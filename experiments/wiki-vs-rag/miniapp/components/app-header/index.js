Component({
  properties: {
    topInset: { type: Number, value: 20 },
    statusLabel: { type: String, value: '正在检查' },
    statusTone: { type: String, value: 'checking' },
  },
  methods: {
    openHistory() { this.triggerEvent('history'); },
    openProfile() { this.triggerEvent('profile'); },
    createConversation() { this.triggerEvent('newconversation'); },
  },
});
