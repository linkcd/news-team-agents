import {
  AgentCoreApplication,
  AgentCoreMcp,
  type AgentCoreProjectSpec,
  type AgentCoreMcpSpec,
} from '@aws/agentcore-cdk';
import { CfnOutput, RemovalPolicy, Stack, type StackProps, aws_iam as iam, aws_logs as logs } from 'aws-cdk-lib';
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

    // Grant collector runtime S3 read/write access for the data bucket
    const collectorEnv = this.application.environments.get('NewsCollector');
    if (collectorEnv) {
      collectorEnv.runtime.addToPolicy(new iam.PolicyStatement({
        actions: ['s3:PutObject', 's3:GetObject'],
        resources: ['arn:aws:s3:::news-agent-data-548129671048/*'],
      }));

      // --- Observability: Tracing + Log Delivery ---
      const runtimeArn = collectorEnv.runtime.runtimeArn;

      // Tracing delivery to X-Ray
      const tracesSource = new logs.CfnDeliverySource(this, 'TracesSource', {
        name: 'newscollector-traces-source',
        resourceArn: runtimeArn,
        logType: 'TRACES',
      });

      const tracesDestination = new logs.CfnDeliveryDestination(this, 'TracesDestination', {
        name: 'newscollector-traces-destination',
        deliveryDestinationType: 'XRAY',
      });

      new logs.CfnDelivery(this, 'TracesDelivery', {
        deliverySourceName: tracesSource.name,
        deliveryDestinationArn: tracesDestination.attrArn,
      });

      // Application log delivery to CloudWatch
      const logGroup = new logs.LogGroup(this, 'AppLogsGroup', {
        logGroupName: `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/${collectorEnv.runtime.runtimeId}`,
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: RemovalPolicy.RETAIN,
      });

      const logsSource = new logs.CfnDeliverySource(this, 'LogsSource', {
        name: 'newscollector-logs-source',
        resourceArn: runtimeArn,
        logType: 'APPLICATION_LOGS',
      });

      const logsDestination = new logs.CfnDeliveryDestination(this, 'LogsDestination', {
        name: 'newscollector-logs-destination',
        destinationResourceArn: logGroup.logGroupArn,
      });

      new logs.CfnDelivery(this, 'LogsDelivery', {
        deliverySourceName: logsSource.name,
        deliveryDestinationArn: logsDestination.attrArn,
      });
    }

    // Stack-level output
    new CfnOutput(this, 'StackNameOutput', {
      description: 'Name of the CloudFormation Stack',
      value: this.stackName,
    });
  }
}
