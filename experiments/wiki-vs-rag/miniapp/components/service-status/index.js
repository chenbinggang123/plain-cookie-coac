Component({
  properties: {
    visible: { type: Boolean, value: false },
    tone: { type: String, value: 'warning' },
    title: { type: String, value: '' },
    detail: { type: String, value: '' },
    actionLabel: { type: String, value: '重试' },
  },
  methods: { handleAction() { this.triggerEvent('action'); } },
});
