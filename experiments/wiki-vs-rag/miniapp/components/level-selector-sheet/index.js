Component({
  properties: { open: { type: Boolean, value: false }, selected: { type: String, value: 'auto' } },
  data: {
    options: [
      { value: 'auto', title: '自动匹配', detail: '根据历史画像和问题中的水平线索决定' },
      { value: '1', title: 'L1 直接告诉我怎么做', detail: '给出清晰动作和最关键的原因' },
      { value: '2', title: 'L2 教我判断条件', detail: '说明组合条件、否决信号和替代方案' },
      { value: '3', title: 'L3 分析权衡与机会成本', detail: '比较动态选择、代价和反事实' },
    ],
  },
  methods: {
    close() { this.triggerEvent('close'); },
    stop() {},
    choose(event) { this.triggerEvent('select', { value: event.currentTarget.dataset.value }); },
  },
});
