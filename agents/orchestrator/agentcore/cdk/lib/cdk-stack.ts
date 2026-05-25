import {
  AgentCoreApplication,
  AgentCoreMcp,
  type AgentCoreProjectSpec,
  type AgentCoreMcpSpec,
} from '@aws/agentcore-cdk';
import {
  CfnOutput,
  Duration,
  RemovalPolicy,
  Stack,
  type StackProps,
  aws_events as events,
  aws_events_targets as targets,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

export interface AgentCoreStackProps extends StackProps {
  /**
   * The AgentCore project specification containing agents, memories, and credentials.
   */
  spec: AgentCoreProjectSpec;
  /**
   * The MCP specification containing gateways and servers.
   */
  mcpSpec?: AgentCoreMcpSpec;
  /**
   * Credential provider ARNs from deployed state, keyed by credential name.
   */
  credentials?: Record<string, { credentialProviderArn: string; clientSecretArn?: string }>;
}

/**
 * CDK Stack that deploys AgentCore infrastructure.
 *
 * This is a thin wrapper that instantiates L3 constructs.
 * All resource logic and outputs are contained within the L3 constructs.
 */
export class AgentCoreStack extends Stack {
  /** The AgentCore application containing all agent environments */
  public readonly application: AgentCoreApplication;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);

    const { spec, mcpSpec, credentials } = props;

    // Create AgentCoreApplication with all agents
    this.application = new AgentCoreApplication(this, 'Application', {
      spec,
    });

    // Create AgentCoreMcp if there are gateways configured
    if (mcpSpec?.agentCoreGateways && mcpSpec.agentCoreGateways.length > 0) {
      new AgentCoreMcp(this, 'Mcp', {
        projectName: spec.name,
        mcpSpec,
        agentCoreApplication: this.application,
        credentials,
        projectTags: spec.tags,
      });
    }

    // Grant orchestrator permission to invoke downstream agents (Collector + Publisher)
    const orchestratorEnv = this.application.environments.get('NewsOrchestrator');
    if (orchestratorEnv) {
      orchestratorEnv.runtime.addToPolicy(new iam.PolicyStatement({
        actions: [
          'bedrock-agentcore:InvokeAgentRuntime',
          'bedrock-agentcore:InvokeAgentRuntimeForUser',
          'bedrock-agentcore:GetAgentCard',
        ],
        resources: [
          'arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newscollector_NewsCollector-EhrHzp4oFi',
          'arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newscollector_NewsCollector-EhrHzp4oFi/*',
          'arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newspublisher_NewsPublisher-OZnqGfD4D2',
          'arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newspublisher_NewsPublisher-OZnqGfD4D2/*',
        ],
      }));

      // --- Observability: Tracing + Log Delivery ---
      const runtimeArn = orchestratorEnv.runtime.runtimeArn;

      // Tracing delivery to X-Ray
      const tracesSource = new logs.CfnDeliverySource(this, 'TracesSource', {
        name: 'newsorchestrator-traces-source',
        resourceArn: runtimeArn,
        logType: 'TRACES',
      });

      const tracesDestination = new logs.CfnDeliveryDestination(this, 'TracesDestination', {
        name: 'newsorchestrator-traces-destination',
        deliveryDestinationType: 'XRAY',
      });

      new logs.CfnDelivery(this, 'TracesDelivery', {
        deliverySourceName: tracesSource.name,
        deliveryDestinationArn: tracesDestination.attrArn,
      });

      // Application log delivery to CloudWatch
      const logGroup = new logs.LogGroup(this, 'AppLogsGroup', {
        logGroupName: `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/${orchestratorEnv.runtime.runtimeId}`,
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: RemovalPolicy.RETAIN,
      });

      const logsSource = new logs.CfnDeliverySource(this, 'LogsSource', {
        name: 'newsorchestrator-logs-source',
        resourceArn: runtimeArn,
        logType: 'APPLICATION_LOGS',
      });

      const logsDestination = new logs.CfnDeliveryDestination(this, 'LogsDestination', {
        name: 'newsorchestrator-logs-destination',
        destinationResourceArn: logGroup.logGroupArn,
      });

      new logs.CfnDelivery(this, 'LogsDelivery', {
        deliverySourceName: logsSource.name,
        deliveryDestinationArn: logsDestination.attrArn,
      });
    }

    // EventBridge schedule: invoke orchestrator every 6 hours
    const orchestratorRuntime = this.application.environments.get('NewsOrchestrator')!.runtime;
    const orchestratorArn = orchestratorRuntime.runtimeArn;

    const invokerFn = new lambda.Function(this, 'ScheduleInvoker', {
      functionName: 'news-agent-schedule-invoker',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      timeout: Duration.seconds(30),
      environment: {
        ORCHESTRATOR_RUNTIME_ARN: orchestratorArn,
      },
      code: lambda.Code.fromInline(`
import json
import os
import uuid
import boto3
from botocore.config import Config
from datetime import datetime, timezone

def handler(event, context):
    runtime_arn = os.environ['ORCHESTRATOR_RUNTIME_ARN']
    client = boto3.client('bedrock-agentcore', region_name='eu-west-1',
        config=Config(read_timeout=10, connect_timeout=10))
    run_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    session_id = f'schedule-{run_time}-{uuid.uuid4().hex[:8]}'
    payload = json.dumps({
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'message/send',
        'params': {
            'message': {
                'messageId': f'msg-{uuid.uuid4().hex[:12]}',
                'role': 'user',
                'parts': [{'data': {'trigger': 'scheduled', 'run_time': run_time}}],
            }
        },
    })
    try:
        client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=payload,
        )
    except Exception as e:
        if 'timed out' in str(e).lower() or 'timeout' in str(e).lower():
            print(f'Request sent, read timed out as expected (fire-and-forget)')
        else:
            raise
    print(f'Triggered orchestrator run_time={run_time} session={session_id}')
    return {'statusCode': 200, 'body': f'Triggered: {run_time}'}
`),
    });

    invokerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:InvokeAgentRuntime'],
      resources: [orchestratorArn, `${orchestratorArn}/*`],
    }));

    new events.Rule(this, 'ScheduleRule', {
      ruleName: 'news-agent-6h-schedule',
      schedule: events.Schedule.cron({ minute: '0', hour: '5,11,17,23' }),
      targets: [new targets.LambdaFunction(invokerFn)],
    });

    // Stack-level output
    new CfnOutput(this, 'StackNameOutput', {
      description: 'Name of the CloudFormation Stack',
      value: this.stackName,
    });
  }
}
