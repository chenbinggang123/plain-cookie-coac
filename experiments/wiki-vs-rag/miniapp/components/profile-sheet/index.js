Component({
  properties: {
    open: { type: Boolean, value: false },
    profile: { type: Object, value: {} },
    dimensions: { type: Array, value: [] },
    loading: { type: Boolean, value: false },
    error: { type: String, value: '' },
    updatingDimension: { type: String, value: '' },
    currentHero: { type: String, value: '全英雄' },
  },
  data: { heroDraft: '全英雄' },
  observers: {
    currentHero(value) { this.setData({ heroDraft: value || '全英雄' }); },
  },
  methods: {
    close() { this.triggerEvent('close'); }, stop() {}, retry() { this.triggerEvent('retry'); },
    inputHero(event) { this.setData({ heroDraft: event.detail.value || '' }); },
    commitHero(event) {
      const hero = String(event.detail.value || this.data.heroDraft || '全英雄').trim() || '全英雄';
      if (hero !== this.properties.currentHero) this.triggerEvent('herochange', { hero });
    },
    setLevel(event) {
      this.triggerEvent('levelchange', { dimension: event.currentTarget.dataset.dimension, level: Number(event.currentTarget.dataset.level) });
    },
  },
});
