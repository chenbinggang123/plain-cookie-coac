Component({
  properties: {
    state: { type: String, value: 'idle' },
    message: { type: String, value: '' },
  },
  methods: {
    choose(event) {
      if (this.properties.state === 'submitting' || this.properties.state === 'success') return;
      this.triggerEvent('submit', { feedback: event.currentTarget.dataset.value });
    },
  },
});
