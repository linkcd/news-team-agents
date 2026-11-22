const { test } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const YAML = require('yaml');
const { useS3Defaults } = require('../dist/bootstrap.js');

function defaultTemplate() {
  return YAML.parse(execFileSync(path.resolve(__dirname, '../node_modules/.bin/cdk'),
    ['bootstrap', '--show-template'], { encoding: 'utf8' }));
}

test('bootstrap leaves encryption to S3 while preserving all other resource controls', () => {
  const original = defaultTemplate();
  const result = useS3Defaults(original);
  assert.equal(result.Resources.StagingBucket.Properties.BucketEncryption, undefined);
  assert.deepEqual(result.Parameters.FileAssetsBucketKmsKeyId.AllowedValues, ['AWS_MANAGED_KEY']);
  assert.equal(result.Parameters.FileAssetsBucketKmsKeyId.Default, 'AWS_MANAGED_KEY');
  assert.notEqual(result.Parameters.BootstrapVariant.Default, original.Parameters.BootstrapVariant.Default);
  assert.ok(original.Resources.StagingBucket.Properties.BucketEncryption, 'must not mutate the input');

  const expected = structuredClone(original);
  delete expected.Resources.StagingBucket.Properties.BucketEncryption;
  expected.Parameters.FileAssetsBucketKmsKeyId = result.Parameters.FileAssetsBucketKmsKeyId;
  expected.Parameters.BootstrapVariant = result.Parameters.BootstrapVariant;
  assert.deepEqual(result, expected, 'IAM, public access, TLS, versioning, lifecycle and retention controls must be preserved');
});

test('bootstrap customization rejects an unexpected upstream bucket definition', () => {
  assert.throws(() => useS3Defaults({ Resources: {} }), /bootstrap template/);
});
