import { App } from 'aws-cdk-lib';
import { createStacks, loadConfiguration } from './deployment';

const config = loadConfiguration();
if (process.env.CDK_DEFAULT_ACCOUNT && process.env.CDK_DEFAULT_ACCOUNT !== config.account) {
  throw new Error(`CLI identity does not match deployment account ${config.account}`);
}
createStacks(new App(), config);
