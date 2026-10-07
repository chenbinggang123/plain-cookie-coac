const ENV = require('../config/env');
const mock = require('./mock');

const pending = new Map();
const latest = new Map();

function classifyError(error, statusCode) {
  if (error && error.type) return error;
  const message = (error && error.message) || String(error || '请求失败');
  if (/timeout|超时/i.test(message)) return Object.assign(new Error('分析等待超时了。问题已保留，请检查网络后重试。'), { type: 'timeout' });
  if (statusCode === 401 || statusCode === 403) return Object.assign(new Error('当前登录状态已失效，请重新进入小程序后再试。'), { type: 'auth' });
  if (/network|fail|无法连接|连接被拒绝/i.test(message)) return Object.assign(new Error('无法连接教练服务，请检查网络和 API 地址后重试。'), { type: 'network' });
  return Object.assign(new Error(message), { type: statusCode >= 500 ? 'service' : 'server', statusCode });
}

function request(path, options = {}) {
  const method = options.method || 'GET';
  const dedupeKey = options.dedupeKey;
  if (dedupeKey && pending.has(dedupeKey)) return pending.get(dedupeKey);
  const sequence = (latest.get(path) || 0) + 1;
  latest.set(path, sequence);

  const execute = (attempt = 0) => new Promise((resolve, reject) => {
    const useCloudBase = ENV.transport === 'cloudbase';
    const requestOptions = {
      method,
      data: options.data,
      timeout: options.timeout || ENV.timeout,
      header: {
        'content-type': 'application/json',
        ...(useCloudBase ? { 'X-WX-SERVICE': ENV.serviceName } : {}),
        ...(options.header || {}),
      },
      success(response) {
        const payload = response.data || {};
        if (response.statusCode >= 200 && response.statusCode < 300 && payload.ok) {
          if (options.ignoreStale && latest.get(path) !== sequence) {
            reject(Object.assign(new Error('请求结果已过期'), { type: 'stale' }));
            return;
          }
          resolve(payload.data);
          return;
        }
        reject(classifyError(new Error(payload.error || `请求失败：${response.statusCode}`), response.statusCode));
      },
      fail(error) {
        const normalized = classifyError(error);
        if (method === 'GET' && attempt < ENV.retryCount) {
          setTimeout(() => execute(attempt + 1).then(resolve, reject), 450);
          return;
        }
        reject(normalized);
      },
    };
    if (useCloudBase) {
      requestOptions.config = { env: ENV.cloudbaseEnv };
      requestOptions.path = path;
    } else {
      requestOptions.url = `${ENV.baseURL}${path}`;
    }
    const task = useCloudBase
      ? wx.cloud.callContainer(requestOptions)
      : wx.request(requestOptions);
    if (options.onTask) options.onTask(task);
  });

  const promise = execute().finally(() => {
    if (dedupeKey) pending.delete(dedupeKey);
  });
  if (dedupeKey) pending.set(dedupeKey, promise);
  return promise;
}

function getStatus() {
  if (ENV.useMock) return mock.status(ENV.mockScenario);
  return request('/api/status', { ignoreStale: true });
}

function getProfile(userId, hero) {
  if (ENV.useMock) return mock.profile(userId, hero, ENV.mockScenario);
  return request(`/api/profile?user_id=${encodeURIComponent(userId)}&hero=${encodeURIComponent(hero)}`, { ignoreStale: true });
}

function setProfileLevel(data) {
  if (ENV.useMock) return mock.setProfile(data);
  return request('/api/profile', { method: 'POST', data, dedupeKey: `profile:${data.dimension}` });
}

function runCoach(data) {
  if (ENV.useMock) return mock.coachRun(data, ENV.mockScenario);
  return request('/api/coach/run', { method: 'POST', data, dedupeKey: 'coach-run', timeout: 180000 });
}

function submitFeedback(data) {
  if (ENV.useMock) return mock.feedback(data, ENV.mockScenario);
  return request('/api/feedback', { method: 'POST', data, dedupeKey: `feedback:${data.run_id}` });
}

function buildIndex(data = {}) {
  if (ENV.useMock) return mock.buildIndex(data);
  return request('/api/index', { method: 'POST', data, dedupeKey: 'build-index', timeout: 180000 });
}

module.exports = { buildIndex, getProfile, getStatus, runCoach, setProfileLevel, submitFeedback };
