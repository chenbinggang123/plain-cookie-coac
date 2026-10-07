/**
 * 开发演示默认使用契约一致的本地 mock，不包含任何模型密钥。
 * CloudBase 上线时将 useMock 改为 false，并填写环境 ID 与云托管服务名。
 */
module.exports = {
  useMock: true,
  mockScenario: 'ready',
  transport: 'cloudbase',
  cloudbaseEnv: 'replace-with-your-cloudbase-env-id',
  serviceName: 'plain-cookie-coach',
  baseURL: 'https://coach-api.example.com',
  timeout: 45000,
  retryCount: 1,
};
