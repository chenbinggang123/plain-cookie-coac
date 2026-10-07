Component({
  properties: { open: { type: Boolean, value: false }, conversations: { type: Array, value: [] }, activeId: { type: String, value: '' }, topInset: { type: Number, value: 20 } },
  methods: {
    close() { this.triggerEvent('close'); }, stop() {}, create() { this.triggerEvent('newconversation'); },
    select(event) { this.triggerEvent('select', { id: event.currentTarget.dataset.id }); },
    remove(event) { this.triggerEvent('delete', { id: event.currentTarget.dataset.id }); },
  },
});
