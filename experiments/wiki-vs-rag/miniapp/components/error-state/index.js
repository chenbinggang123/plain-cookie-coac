Component({
  properties: {
    title: { type: String, value: '这次分析没有完成' },
    detail: { type: String, value: '你的问题已经保留，可以直接重试。' },
    actionLabel: { type: String, value: '重新分析' },
  },
  methods: { retry() { this.triggerEvent('retry'); } },
});
