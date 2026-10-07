const api = require('../../services/api');
const conversations = require('../../services/conversations');
const { buildCoachMessage, formatTime, levelLabel } = require('../../utils/format');

const DEFAULT_SUGGESTIONS = [
  '李白逆风时应该怎么找翻盘点？',
  '貂蝉四级第一波没抓到人，下一步做什么？',
  '对面中辅一直跟野区，打野该怎么发育？',
  '我玩射手经济第一，团战为什么总是暴毙？',
];

const DIMENSION_DESCRIPTIONS = {
  mechanics: '技能衔接、走位、连招与操作稳定性',
  economy: '刷野、兵线、经济与资源转换',
  decision: '入侵、抓边、接团、撤退与风险判断',
};

function conversationId() {
  return `conversation-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function profileDimensions(profile) {
  return Object.keys((profile && profile.dimensions) || {}).map((key) => {
    const item = profile.dimensions[key];
    const current = Number(item.level || 2);
    return {
      ...item,
      key,
      description: DIMENSION_DESCRIPTIONS[key] || item.description,
      confidenceText: `${Math.round(Number(item.confidence || 0) * 100)}%`,
      levelLabel: item.level_label || levelLabel(current),
      levelOptions: [1, 2, 3].map((value) => ({ value, active: value === current })),
    };
  });
}

function historyRows(items) {
  return items.map((item) => ({ ...item, timeLabel: formatTime(item.updatedAt) }));
}

Page({
  data: {
    topInset: 20,
    headerHeight: 68,
    composerHeight: 104,
    messages: [],
    draft: '',
    scrollTarget: 'chat-start',
    suggestions: DEFAULT_SUGGESTIONS,
    busy: false,
    generationStage: '正在判断局面…',
    requestError: null,
    lastFailedQuestion: '',
    selectedLevel: 'auto',
    selectedLevelLabel: '自动匹配',
    levelSheetOpen: false,
    profileSheetOpen: false,
    profileLoading: false,
    profileError: '',
    profile: {},
    dimensions: [],
    updatingDimension: '',
    historyOpen: false,
    history: [],
    conversationId: '',
    statusLabel: '正在检查',
    statusTone: 'checking',
    statusReady: false,
    serviceBanner: { visible: false, tone: 'warning', title: '', detail: '', actionLabel: '重新检查' },
    online: true,
    currentHero: '全英雄',
  },

  onLoad() {
    const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    const topInset = Number(info.statusBarHeight || 20);
    const safeBottom = info.safeArea ? Math.max(0, Number(info.screenHeight || info.windowHeight) - Number(info.safeArea.bottom || info.windowHeight)) : 0;
    const app = getApp();
    this.setData({ topInset, headerHeight: topInset + 48, composerHeight: 104 + safeBottom, conversationId: conversationId(), currentHero: app.globalData.hero || '全英雄' });
    this.refreshHistory();
    this.loadStatus();
    this.loadProfile();
    this.networkHandler = (state) => this.handleNetworkChange(state);
    wx.onNetworkStatusChange(this.networkHandler);
    wx.getNetworkType({ success: ({ networkType }) => this.handleNetworkChange({ isConnected: networkType !== 'none', networkType }) });
  },

  onUnload() {
    if (this.networkHandler && wx.offNetworkStatusChange) wx.offNetworkStatusChange(this.networkHandler);
    this.clearStageTimers();
  },

  async loadStatus() {
    if (!this.data.online) return;
    this.setData({ statusLabel: '正在检查', statusTone: 'checking' });
    try {
      const status = await api.getStatus();
      const ready = Boolean(status.index_ready && !status.index_stale);
      let banner = { visible: false, tone: 'warning', title: '', detail: '', actionLabel: '重新检查' };
      let statusLabel = '已就绪';
      let statusTone = 'ready';
      if (!status.index_ready) {
        statusLabel = '需要创建索引';
        statusTone = 'warning';
        banner = { visible: true, tone: 'warning', title: '知识索引尚未创建', detail: '请联系服务管理员创建索引，完成后在这里重新检查。', actionLabel: '重新检查' };
      } else if (status.index_stale) {
        statusLabel = '知识库更新中';
        statusTone = 'warning';
        banner = { visible: true, tone: 'warning', title: '知识库已更新，索引需要同步', detail: '管理员完成索引更新后即可继续提问。', actionLabel: '重新检查' };
      }
      this.setData({
        statusLabel,
        statusTone,
        statusReady: ready,
        serviceBanner: banner,
        suggestions: status.sample_questions && status.sample_questions.length ? status.sample_questions : DEFAULT_SUGGESTIONS,
      });
    } catch (error) {
      this.setData({
        statusLabel: '服务不可用',
        statusTone: 'error',
        statusReady: false,
        serviceBanner: { visible: true, tone: 'error', title: '暂时无法连接教练服务', detail: error.message || '请检查网络后重试。', actionLabel: '重试' },
      });
    }
  },

  async loadProfile() {
    this.setData({ profileLoading: true, profileError: '' });
    try {
      const app = getApp();
      const profile = await api.getProfile(app.globalData.userId, app.globalData.hero);
      this.setData({ profile, dimensions: profileDimensions(profile), profileLoading: false });
    } catch (error) {
      this.setData({ profileLoading: false, profileError: error.message || '能力画像暂时没有加载成功。' });
    }
  },

  handleNetworkChange(state) {
    const online = Boolean(state.isConnected);
    if (!online) {
      this.setData({
        online,
        statusLabel: '网络已断开',
        statusTone: 'error',
        statusReady: false,
        serviceBanner: { visible: true, tone: 'error', title: '当前没有网络连接', detail: '问题会保留在输入框里。恢复网络后点击重试。', actionLabel: '重新检查' },
      });
    } else if (!this.data.online) {
      this.setData({ online });
      this.loadStatus();
    } else {
      this.setData({ online });
    }
  },

  chooseSuggestion(event) {
    this.setData({ draft: event.detail.question || '' });
  },

  handleDraftChange(event) {
    this.setData({ draft: event.detail.value || '' });
  },

  openLevelSheet() { this.setData({ levelSheetOpen: true }); },
  closeLevelSheet() { this.setData({ levelSheetOpen: false }); },
  selectLevel(event) {
    const value = event.detail.value;
    const labels = { auto: '自动匹配', 1: 'L1 直接告诉我怎么做', 2: 'L2 教我判断条件', 3: 'L3 分析权衡与机会成本' };
    this.setData({ selectedLevel: value, selectedLevelLabel: labels[value], levelSheetOpen: false });
  },

  async sendQuestion(event) {
    const text = (event.detail.text || '').trim();
    if (!text || this.data.busy) return;
    if (!this.data.online) {
      this.setData({ requestError: { title: '当前没有网络连接', detail: '问题已保留。恢复网络后点击重新分析。' }, lastFailedQuestion: text });
      return;
    }
    if (!this.data.statusReady) {
      this.setData({ draft: text });
      wx.showToast({ title: '教练服务还没准备好', icon: 'none' });
      return;
    }

    const userMessage = { id: `user-${Date.now()}`, role: 'user', text, createdAt: Date.now() };
    const messages = [...this.data.messages, userMessage];
    this.setData({ messages, draft: '', busy: true, requestError: null, lastFailedQuestion: text, generationStage: '正在识别问题…' });
    this.startStageTimers();
    this.scrollToBottom();

    try {
      const app = getApp();
      const result = await api.runCoach({
        question: text,
        user_id: app.globalData.userId,
        hero: app.globalData.hero,
        declared_level: this.data.selectedLevel === 'auto' ? null : Number(this.data.selectedLevel),
      });
      const resolvedHero = result.personalization && result.personalization.hero;
      if (resolvedHero && resolvedHero !== this.data.currentHero) {
        app.globalData.hero = resolvedHero;
        this.setData({ currentHero: resolvedHero });
      }
      const coachMessage = buildCoachMessage(result);
      const nextMessages = [...this.data.messages, coachMessage];
      this.setData({ messages: nextMessages, busy: false, requestError: null });
      this.persistConversation(nextMessages);
      this.loadProfile();
    } catch (error) {
      if (error.type !== 'stale') {
        this.setData({
          busy: false,
          requestError: { title: '这次分析没有完成', detail: error.message || '问题已保留，可以直接重试。' },
        });
      }
    } finally {
      this.clearStageTimers();
      this.scrollToBottom();
    }
  },

  retryQuestion() {
    const text = this.data.lastFailedQuestion;
    if (!text) return;
    const withoutFailedDuplicate = [...this.data.messages];
    const last = withoutFailedDuplicate[withoutFailedDuplicate.length - 1];
    if (last && last.role === 'user' && last.text === text) withoutFailedDuplicate.pop();
    this.setData({ messages: withoutFailedDuplicate, requestError: null }, () => this.sendQuestion({ detail: { text } }));
  },

  startStageTimers() {
    this.clearStageTimers();
    this.stageTimers = [
      setTimeout(() => this.setData({ generationStage: '正在检索知识库…' }), 450),
      setTimeout(() => this.setData({ generationStage: '正在组织适合你的讲解…' }), 950),
    ];
  },

  clearStageTimers() {
    (this.stageTimers || []).forEach((timer) => clearTimeout(timer));
    this.stageTimers = [];
  },

  scrollToBottom() {
    this.setData({ scrollTarget: '' }, () => {
      wx.nextTick(() => this.setData({ scrollTarget: 'chat-bottom' }));
    });
  },

  handleKeyboard(event) {
    if (event.detail.height > 0) this.scrollToBottom();
  },

  copyAnswer(event) {
    wx.setClipboardData({ data: event.detail.text || '', success: () => wx.showToast({ title: '回答已复制', icon: 'success' }) });
  },

  async submitFeedback(event) {
    const { messageId, feedback } = event.detail;
    const index = this.data.messages.findIndex((item) => item.id === messageId);
    if (index < 0) return;
    const message = this.data.messages[index];
    if (message.feedbackState === 'submitting' || message.feedbackState === 'success') return;
    this.updateMessage(index, { feedbackState: 'submitting', feedbackMessage: '' });
    try {
      const data = await api.submitFeedback({ run_id: message.runId, user_id: message.userId, hero: message.hero, dimension: message.dimension, feedback });
      this.updateMessage(index, { feedbackState: 'success', feedbackMessage: data.message || '反馈已记录。' });
      if (data.profile) this.setData({ profile: data.profile, dimensions: profileDimensions(data.profile) });
      this.persistConversation(this.data.messages);
    } catch (error) {
      this.updateMessage(index, { feedbackState: 'error', feedbackMessage: error.message || '反馈提交失败，请再试一次。' });
    }
  },

  updateMessage(index, patch) {
    const messages = this.data.messages.map((item, current) => current === index ? { ...item, ...patch } : item);
    this.setData({ messages });
  },

  openProfile() { this.setData({ profileSheetOpen: true }); },
  closeProfile() { this.setData({ profileSheetOpen: false }); },

  changeHero(event) {
    const hero = event.detail.hero || '全英雄';
    const app = getApp();
    app.globalData.hero = hero;
    this.setData({ currentHero: hero, profile: {}, dimensions: [] }, () => this.loadProfile());
  },

  async changeProfileLevel(event) {
    const { dimension, level } = event.detail;
    this.setData({ updatingDimension: dimension, profileError: '' });
    try {
      const app = getApp();
      const profile = await api.setProfileLevel({ user_id: app.globalData.userId, hero: app.globalData.hero, dimension, level });
      this.setData({ profile, dimensions: profileDimensions(profile), updatingDimension: '' });
      wx.showToast({ title: '教学深度已更新', icon: 'success' });
    } catch (error) {
      this.setData({ updatingDimension: '', profileError: error.message || '调整失败，请重试。' });
    }
  },

  openHistory() { this.refreshHistory(); this.setData({ historyOpen: true }); },
  closeHistory() { this.setData({ historyOpen: false }); },
  refreshHistory() { this.setData({ history: historyRows(conversations.list()) }); },

  newConversation() {
    if (this.data.messages.length) this.persistConversation(this.data.messages);
    this.clearStageTimers();
    this.setData({ conversationId: conversationId(), messages: [], draft: '', busy: false, requestError: null, historyOpen: false, selectedLevel: 'auto', selectedLevelLabel: '自动匹配' });
  },

  selectConversation(event) {
    const item = conversations.list().find((entry) => entry.id === event.detail.id);
    if (!item) return;
    this.setData({ conversationId: item.id, messages: item.messages || [], historyOpen: false, requestError: null }, () => this.scrollToBottom());
  },

  deleteConversation(event) {
    const id = event.detail.id;
    const target = conversations.list().find((item) => item.id === id);
    if (!target) return;
    wx.showModal({
      title: '删除这次复盘？',
      content: `“${target.title}”删除后无法恢复。`,
      confirmText: '删除',
      confirmColor: '#A94A3F',
      success: ({ confirm }) => {
        if (!confirm) return;
        conversations.remove(id);
        if (id === this.data.conversationId) this.setData({ conversationId: conversationId(), messages: [], requestError: null });
        this.refreshHistory();
      },
    });
  },

  persistConversation(messages) {
    if (!messages.some((item) => item.role === 'user')) return;
    conversations.save({ id: this.data.conversationId, messages });
    this.refreshHistory();
  },
});
