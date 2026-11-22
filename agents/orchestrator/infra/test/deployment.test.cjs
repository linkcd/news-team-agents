const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { App } = require('aws-cdk-lib');
const { Template, Match } = require('aws-cdk-lib/assertions');
const { createStacks, loadConfiguration } = require('../dist/deployment.js');
const testConfiguration = () => ({
  account: '0'.repeat(12), region: 'eu-west-1', bucketName: 'news-agent-test-data',
  blogRepo: 'example/blog', blogBranch: 'main', workflowFile: 'deploy.yml',
  modelId: 'global.anthropic.claude-sonnet-4-6', scheduleEnabled: false, publishingEnabled: false,
});

test('deployment settings are loaded from a supplied private configuration file', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'news-deployment-test-'));
  try {
    const file = path.join(dir, 'deployment.json');
    fs.writeFileSync(file, JSON.stringify(testConfiguration()));
    const actual = loadConfiguration(file);
    assert.equal(actual.account === testConfiguration().account, true);
    assert.equal(actual.blogRepo === testConfiguration().blogRepo, true);
  } finally {
    fs.rmSync(dir, {recursive: true, force: true});
  }
});

test('foundation provisions retained private data with seven-day expiry', () => {
  const stacks = createStacks(new App(), testConfiguration());
  Template.fromStack(stacks.foundation).hasResourceProperties('AWS::S3::Bucket', {
    BucketName: 'news-agent-test-data',
    BucketEncryption: Match.absent(),
    VersioningConfiguration: { Status: 'Enabled' },
    LifecycleConfiguration: { Rules: Match.arrayWith([{
      ExpirationInDays: 7, NoncurrentVersionExpiration: { NoncurrentDays: 7 }, Status: 'Enabled',
    }]) },
    PublicAccessBlockConfiguration: {
      BlockPublicAcls: true, BlockPublicPolicy: true, IgnorePublicAcls: true, RestrictPublicBuckets: true,
    },
  });
  Template.fromStack(stacks.foundation).hasResource('AWS::S3::Bucket', {DeletionPolicy: 'Retain'});
});

test('runtimes use supplied settings and dry-run mode keeps the schedule disabled', () => {
  const stacks = createStacks(new App(), testConfiguration());
  for (const stack of Object.values(stacks)) {
    const template = Template.fromStack(stack).toJSON();
    assert.equal(stack.account, testConfiguration().account);
  }
  Template.fromStack(stacks.publisher).hasResourceProperties('AWS::BedrockAgentCore::Runtime', {
    EnvironmentVariables: Match.objectLike({BLOG_REPO: 'example/blog', PUBLISHING_ENABLED: 'false'}),
  });
  Template.fromStack(stacks.orchestrator).hasResourceProperties('AWS::BedrockAgentCore::Runtime', {
    EnvironmentVariables: Match.objectLike({
      BLOG_REPO: 'example/blog', S3_BUCKET: 'news-agent-test-data',
      COLLECTOR_RUNTIME_ARN: Match.anyValue(), PUBLISHER_RUNTIME_ARN: Match.anyValue(),
    }),
  });
  Template.fromStack(stacks.orchestrator).hasResourceProperties('AWS::Events::Rule', {
    State: 'DISABLED', ScheduleExpression: 'cron(0 5,11,17,23 * * ? *)',
  });
});

test('live mode enables publishing and the regular schedule together', () => {
  const stacks = createStacks(new App(), {...testConfiguration(), scheduleEnabled: true, publishingEnabled: true});
  Template.fromStack(stacks.publisher).hasResourceProperties('AWS::BedrockAgentCore::Runtime', {
    EnvironmentVariables: Match.objectLike({BLOG_REPO: 'example/blog', PUBLISHING_ENABLED: 'true'}),
  });
  Template.fromStack(stacks.orchestrator).hasResourceProperties('AWS::Events::Rule', {
    State: 'ENABLED', ScheduleExpression: 'cron(0 5,11,17,23 * * ? *)',
  });
});

test('enabling schedule requires publishing to be enabled too', () => {
  assert.throws(() => createStacks(new App(), {
    ...testConfiguration(), scheduleEnabled: true, publishingEnabled: false,
  }), /publishing/);
});

test('orchestrator and scheduler can invoke the DEFAULT runtime endpoints', () => {
  const stacks = createStacks(new App(), testConfiguration());
  const template = Template.fromStack(stacks.orchestrator);
  const policies = Object.values(template.findResources('AWS::IAM::Policy'));
  function endpointGrants(rolePrefix) {
    return policies
      .filter(p => p.Properties.Roles.some(role => role.Ref?.startsWith(rolePrefix)))
      .flatMap(p => p.Properties.PolicyDocument.Statement)
      .filter(s => s.Effect === 'Allow' && [].concat(s.Action).includes('bedrock-agentcore:InvokeAgentRuntime'))
      .flatMap(s => [].concat(s.Resource))
      .filter(r => JSON.stringify(r).includes('/runtime-endpoint/DEFAULT'));
  }
  assert.equal(endpointGrants('AgentRuntimeExecutionRole').length, 2);
  assert.equal(endpointGrants('ScheduleInvokerServiceRole').length, 1);
});

test('orchestrator can verify collection receipts only under the collection prefix', () => {
  const { orchestrator } = createStacks(new App(), testConfiguration());
  const policies = Object.values(Template.fromStack(orchestrator).findResources('AWS::IAM::Policy'));
  const reads = policies.filter(p => p.Properties.Roles.some(r => r.Ref?.startsWith('AgentRuntimeExecutionRole')))
    .flatMap(p => p.Properties.PolicyDocument.Statement)
    .filter(s => s.Effect === 'Allow' && [].concat(s.Action).includes('s3:GetObject'));
  assert.equal(reads.length, 1);
  assert.ok(JSON.stringify(reads[0].Resource).includes('news-agent-test-data/collections/*'));
});
