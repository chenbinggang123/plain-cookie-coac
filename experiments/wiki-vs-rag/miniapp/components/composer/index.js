Component({
  properties: {
    busy: { type: Boolean, value: false },
    levelLabel: { type: String, value: '自动匹配' },
    value: { type: String, value: '' },
  },
  data: { draft: '', length: 0, nearLimit: false, canSend: false },
  observers: {
    value(value) {
      if (value !== this.data.draft) {
        const draft = value || '';
        this.setData({ draft, length: draft.length, nearLimit: draft.length >= 1100, canSend: Boolean(draft.trim()) });
      }
    },
  },
  methods: {
    handleInput(event) {
      const draft = event.detail.value || '';
      this.setData({ draft, length: draft.length, nearLimit: draft.length >= 1100, canSend: Boolean(draft.trim()) });
      this.triggerEvent('change', { value: draft });
    },
    openLevel() { if (!this.properties.busy) this.triggerEvent('level'); },
    send() {
      const text = this.data.draft.trim();
      if (!text || this.properties.busy) return;
      this.triggerEvent('send', { text });
    },
    keyboardChange(event) { this.triggerEvent('keyboard', { height: event.detail.height || 0 }); },
  },
});
