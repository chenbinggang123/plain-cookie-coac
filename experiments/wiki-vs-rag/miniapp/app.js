const ENV = require('./config/env');

App({
  onLaunch() {
    if (!ENV.useMock && ENV.transport === 'cloudbase') {
      wx.cloud.init({ env: ENV.cloudbaseEnv, traceUser: true });
    }
  },
  globalData: {
    userId: 'local-user',
    hero: '全英雄',
  },
});
