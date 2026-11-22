// Copyright 2026 news-agent contributors
// SPDX-License-Identifier: Apache-2.0
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parse, stringify } from 'yaml';

type BootstrapTemplate = {
  Parameters: Record<string, { Default?: string; AllowedValues?: string[]; [key: string]: unknown }>;
  Resources: Record<string, { Type: string; Properties: Record<string, unknown> }>;
  [key: string]: unknown;
};

export function useS3Defaults(input: unknown): BootstrapTemplate {
  const template = structuredClone(input) as BootstrapTemplate;
  const bucket = template?.Resources?.StagingBucket;
  const key = template?.Parameters?.FileAssetsBucketKmsKeyId;
  const variant = template?.Parameters?.BootstrapVariant;
  if (bucket?.Type !== 'AWS::S3::Bucket' || !bucket.Properties?.BucketEncryption || !key || !variant) {
    throw new Error('Unexpected CDK bootstrap template; review the upstream bucket configuration');
  }

  // Do not request PutBucketEncryption. S3 applies automatic SSE-S3 encryption
  // and retains the account/service defaults, including blocked encryption types.
  delete bucket.Properties.BucketEncryption;
  // Keep the standard CLI parameter contract, but prevent creation or selection
  // of a KMS key for this S3-default variant. Existing key resources are conditional.
  key.Default = 'AWS_MANAGED_KEY';
  key.AllowedValues = ['AWS_MANAGED_KEY'];
  variant.Default = 'NewsAgent: S3 automatic encryption v1';
  return template;
}

if (require.main === module) {
  const source = execFileSync(resolve(__dirname, '../node_modules/.bin/cdk'),
    ['bootstrap', '--show-template'], { encoding: 'utf8' });
  const output = resolve(__dirname, 'bootstrap-s3-default.yaml');
  writeFileSync(output, stringify(useS3Defaults(parse(source))));
  console.log(`Generated ${output}`);
}
