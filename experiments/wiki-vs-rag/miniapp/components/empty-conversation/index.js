Component({
  properties: { suggestions: { type: Array, value: [] } },
  methods: {
    choose(event) { this.triggerEvent('choose', { question: event.currentTarget.dataset.question }); },
  },
});
