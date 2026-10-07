const assert = require('assert');

const memory = {};
let requestCount = 0;
let cloudRequestCount = 0;
global.wx = {
  getStorageSync(key) { return memory[key]; },
  setStorageSync(key, value) { memory[key] = value; },
  request(options) {
    requestCount += 1;
    setTimeout(() => options.success({ statusCode: 200, data: { ok: true, data: { run_id: 'real-contract' } } }), 5);
    return { abort() {} };
  },
  cloud: {
    callContainer(options) {
      cloudRequestCount += 1;
      assert.strictEqual(options.config.env, 'env-test');
      assert.strictEqual(options.path, '/api/status');
      assert.strictEqual(options.header['X-WX-SERVICE'], 'plain-cookie-coach');
      setTimeout(() => options.success({ statusCode: 200, data: { ok: true, data: { index_ready: true } } }), 5);
      return { abort() {} };
    },
  },
};

const ENV = require('../config/env');
const api = require('../services/api');
const conversations = require('../services/conversations');
const { buildCoachMessage, formatAnswer } = require('../utils/format');

async function main() {
  assert.deepStrictEqual(formatAnswer('## 判断\n1. 先看线权\n\n再看位置').map((item) => item.type), ['heading', 'ordered', 'paragraph']);

  ENV.useMock = true;
  const status = await api.getStatus();
  assert.strictEqual(status.index_ready, true);
  const result = await api.runCoach({ question: '我玩射手经济第一为什么会暴毙？', user_id: 'local-user', hero: '全英雄', declared_level: 2 });
  const message = buildCoachMessage(result);
  assert.strictEqual(message.role, 'coach');
  assert.ok(message.blocks.length >= 5);
  assert.ok(message.evidence.length >= 2);

  memory['jing-coach-conversations-v1'] = [{ id: 'legacy', messages: [] }];
  assert.strictEqual(conversations.list()[0].id, 'legacy');
  assert.ok(Array.isArray(memory['plain-cookie-coach-conversations-v1']), '旧品牌历史应迁移到新存储键');

  const messages = Array.from({ length: 25 }, (_, index) => ({ id: String(index), role: index % 2 ? 'coach' : 'user', text: `消息${index}` }));
  conversations.save({ id: 'one', messages });
  assert.strictEqual(conversations.list()[0].messages.length, 24);

  ENV.useMock = false;
  ENV.transport = 'request';
  const first = api.runCoach({ question: 'A' });
  const second = api.runCoach({ question: 'B' });
  const responses = await Promise.all([first, second]);
  assert.strictEqual(requestCount, 1, '重复提交应复用同一个在途请求');
  assert.strictEqual(responses[0].run_id, 'real-contract');
  assert.strictEqual(responses[1].run_id, 'real-contract');

  ENV.transport = 'cloudbase';
  ENV.cloudbaseEnv = 'env-test';
  const cloudStatus = await api.getStatus();
  assert.strictEqual(cloudStatus.index_ready, true);
  assert.strictEqual(cloudRequestCount, 1, 'CloudBase 请求应通过 callContainer 发送');

  process.stdout.write('miniapp smoke tests passed\n');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
