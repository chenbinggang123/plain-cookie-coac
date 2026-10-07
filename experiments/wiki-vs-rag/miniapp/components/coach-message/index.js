Component({
  properties: { message: { type: Object, value: {} } },
  methods: {
    copyAnswer() { this.triggerEvent('copy', { text: this.properties.message.answer }); },
    submitFeedback(event) {
      this.triggerEvent('feedback', { messageId: this.properties.message.id, feedback: event.detail.feedback });
    },
  },
});
