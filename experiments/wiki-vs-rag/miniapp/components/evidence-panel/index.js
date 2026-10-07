Component({
  properties: {
    rationale: { type: Object, value: {} },
    evidence: { type: Array, value: [] },
    insufficient: { type: Boolean, value: false },
  },
  data: { rationaleOpen: false, sourcesOpen: false, openedIndex: -1 },
  methods: {
    toggleRationale() { this.setData({ rationaleOpen: !this.data.rationaleOpen }); },
    toggleSources() { this.setData({ sourcesOpen: !this.data.sourcesOpen }); },
    toggleItem(event) {
      const index = Number(event.currentTarget.dataset.index);
      this.setData({ openedIndex: this.data.openedIndex === index ? -1 : index });
    },
  },
});
