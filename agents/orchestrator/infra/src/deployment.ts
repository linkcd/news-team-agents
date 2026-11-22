import { AgentEnvironment, AgentCoreProjectSpecSchema } from '@aws/agentcore-cdk';
import {
  App, Stack, CfnOutput, Duration, RemovalPolicy,
  aws_s3 as s3, aws_iam as iam, aws_logs as logs,
  aws_lambda as lambda, aws_events as events, aws_events_targets as targets,
} from 'aws-cdk-lib';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export interface DeploymentConfig {
  account: string;
  region: string;
  bucketName: string;
  blogRepo: string;
  blogBranch: string;
  workflowFile: string;
  modelId: string;
  scheduleEnabled: boolean;
  publishingEnabled: boolean;
}

function validateConfiguration(config: DeploymentConfig): void {
  if (!/^\d{12}$/.test(config.account) || !config.region || !config.bucketName) {
    throw new Error('Deployment requires an account, region and bucketName');
  }
  if (!/^[\w.-]+\/[\w.-]+$/.test(config.blogRepo) || !config.blogBranch || !config.workflowFile || !config.modelId) {
    throw new Error('Deployment requires blogRepo, blogBranch, workflowFile and modelId');
  }
  if (typeof config.scheduleEnabled !== 'boolean' || typeof config.publishingEnabled !== 'boolean') {
    throw new Error('scheduleEnabled and publishingEnabled must be booleans');
  }
  if (config.scheduleEnabled && !config.publishingEnabled) {
    throw new Error('Enable publishing before enabling the schedule');
  }
}

export function loadConfiguration(file = resolve(__dirname, '../deployment.json')): DeploymentConfig {
  if (!existsSync(file)) {
    throw new Error('Create the git-ignored deployment.json from deployment.example.json and supply your private settings');
  }
  const config = JSON.parse(readFileSync(file, 'utf8'));
  validateConfiguration(config);
  return config;
}

function grantDefaultInvocation(runtime: AgentEnvironment['runtime'], grantee: iam.IGrantable): void {
  runtime.grantInvoke(grantee);
  iam.Grant.addToPrincipal({
    grantee,
    actions: ['bedrock-agentcore:InvokeAgentRuntime', 'bedrock-agentcore:InvokeAgentRuntimeForUser'],
    resourceArns: [`${runtime.runtimeArn}/runtime-endpoint/DEFAULT`],
  });
}

function addObservability(stack: Stack, runtime: AgentEnvironment['runtime'], name: string): void {
  const group = new logs.LogGroup(stack, 'ApplicationLogs', {
    logGroupName: `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/${runtime.runtimeId}`,
    retention: logs.RetentionDays.TWO_WEEKS,
    removalPolicy: RemovalPolicy.RETAIN,
  });
  for (const type of ['TRACES', 'APPLICATION_LOGS'] as const) {
    const source = new logs.CfnDeliverySource(stack, `${type}Source`, {
      name: `${name}-${type.toLowerCase()}-source`, resourceArn: runtime.runtimeArn, logType: type,
    });
    const destination = new logs.CfnDeliveryDestination(stack, `${type}Destination`, {
      name: `${name}-${type.toLowerCase()}-destination`,
      ...(type === 'TRACES' ? { deliveryDestinationType: 'XRAY' } : { destinationResourceArn: group.logGroupArn }),
    });
    const delivery = new logs.CfnDelivery(stack, `${type}Delivery`, {
      deliverySourceName: source.name, deliveryDestinationArn: destination.attrArn,
    });
    delivery.node.addDependency(source, destination);
  }
}

function runtimeStack(app: App, kind: string, config: DeploymentConfig) {
  const projectDir = resolve(__dirname, '../../..', kind);
  const spec = AgentCoreProjectSpecSchema.parse(JSON.parse(
    readFileSync(resolve(projectDir, 'agentcore/agentcore.json'), 'utf8'),
  ));
  // The maintained app uses one private configuration for all stacks. Legacy
  // CLI targets and generated CDK state are local-only and are not consumed here.
  const title = kind[0].toUpperCase() + kind.slice(1);
  const stack = new Stack(app, `NewsAgent-${title}`, {
    env: { account: config.account, region: config.region },
  });
  const agent = AgentCoreProjectSpecSchema.parse({
    ...spec,
    runtimes: [{ ...spec.runtimes[0], codeLocation: resolve(projectDir, spec.runtimes[0].codeLocation) }],
  }).runtimes[0];
  const environment = new AgentEnvironment(stack, 'Agent', {
    projectName: spec.name,
    configRoot: resolve(projectDir, 'agentcore'),
    agent,
  });
  const runtime = environment.runtime;
  runtime.addEnvironmentVariable('AWS_REGION', config.region);
  runtime.addEnvironmentVariable('MODEL_ID', config.modelId);
  for (const credential of spec.credentials) {
    runtime.grantCredentialAccess();
    runtime.addEnvironmentVariable(`CREDENTIAL_${credential.name.toUpperCase().replace(/[.-]/g, '_')}_NAME`, credential.name);
  }
  addObservability(stack, runtime, spec.name);
  new CfnOutput(stack, 'RuntimeArn', { value: runtime.runtimeArn });
  new CfnOutput(stack, 'RuntimeId', { value: runtime.runtimeId });
  return { stack, runtime };
}

export function createStacks(app: App, config: DeploymentConfig) {
  validateConfiguration(config);
  const foundation = new Stack(app, 'NewsAgent-Foundation', {
    env: { account: config.account, region: config.region },
  });
  const bucket = new s3.Bucket(foundation, 'DataBucket', {
    bucketName: config.bucketName,
    versioned: true,
    blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    enforceSSL: true,
    removalPolicy: RemovalPolicy.RETAIN,
    lifecycleRules: [{ expiration: Duration.days(7), noncurrentVersionExpiration: Duration.days(7) }],
  });
  // S3 encrypts new objects with SSE-S3 automatically. Leave the bucket's
  // encryption configuration (including the account's SSE-C block) unmanaged.
  // The L2 otherwise emits an explicit AES256 BucketEncryption property.
  (bucket.node.defaultChild as s3.CfnBucket).bucketEncryption = undefined;
  new CfnOutput(foundation, 'BucketName', { value: bucket.bucketName });

  const collector = runtimeStack(app, 'collector', config);
  const publisher = runtimeStack(app, 'publisher', config);
  const orchestrator = runtimeStack(app, 'orchestrator', config);
  collector.stack.addStackDependency(foundation);
  publisher.stack.addStackDependency(foundation);
  const objectsArn = `arn:${foundation.partition}:s3:::${config.bucketName}/*`;
  collector.runtime.addToPolicy(new iam.PolicyStatement({
    actions: ['s3:GetObject', 's3:PutObject'], resources: [objectsArn],
  }));
  publisher.runtime.addToPolicy(new iam.PolicyStatement({ actions: ['s3:GetObject'], resources: [objectsArn] }));
  orchestrator.runtime.addToPolicy(new iam.PolicyStatement({
    actions: ['s3:GetObject'],
    resources: [`arn:${foundation.partition}:s3:::${config.bucketName}/collections/*`],
  }));

  publisher.runtime.addEnvironmentVariable('BLOG_REPO', config.blogRepo);
  publisher.runtime.addEnvironmentVariable('BLOG_BRANCH', config.blogBranch);
  publisher.runtime.addEnvironmentVariable('BLOG_WORKFLOW', config.workflowFile);
  publisher.runtime.addEnvironmentVariable('PUBLISHING_ENABLED', String(config.publishingEnabled));
  const orchestrationConfig = {
    COLLECTOR_RUNTIME_ARN: collector.runtime.runtimeArn,
    PUBLISHER_RUNTIME_ARN: publisher.runtime.runtimeArn,
    S3_BUCKET: config.bucketName,
    BLOG_REPO: config.blogRepo,
    BLOG_BRANCH: config.blogBranch,
  };
  for (const [key, value] of Object.entries(orchestrationConfig)) {
    orchestrator.runtime.addEnvironmentVariable(key, value);
  }
  grantDefaultInvocation(collector.runtime, orchestrator.runtime.role);
  grantDefaultInvocation(publisher.runtime, orchestrator.runtime.role);
  orchestrator.runtime.addToPolicy(new iam.PolicyStatement({
    actions: ['bedrock-agentcore:GetAgentCard'],
    resources: [collector.runtime.runtimeArn, publisher.runtime.runtimeArn,
      `${collector.runtime.runtimeArn}/runtime-endpoint/DEFAULT`,
      `${publisher.runtime.runtimeArn}/runtime-endpoint/DEFAULT`],
  }));

  const invoker = new lambda.Function(orchestrator.stack, 'ScheduleInvoker', {
    functionName: 'news-agent-schedule-invoker', runtime: lambda.Runtime.PYTHON_3_12,
    handler: 'invoker.handler', code: lambda.Code.fromAsset(resolve(__dirname, '../lambda')),
    timeout: Duration.seconds(30), retryAttempts: 0,
    environment: { ORCHESTRATOR_RUNTIME_ARN: orchestrator.runtime.runtimeArn },
  });
  grantDefaultInvocation(orchestrator.runtime, invoker);
  new events.Rule(orchestrator.stack, 'ScheduleRule', {
    ruleName: 'news-agent-6h-schedule', enabled: config.scheduleEnabled,
    schedule: events.Schedule.cron({ minute: '0', hour: '5,11,17,23' }),
    targets: [new targets.LambdaFunction(invoker, { retryAttempts: 0 })],
  });

  return { foundation, collector: collector.stack, publisher: publisher.stack, orchestrator: orchestrator.stack };
}
