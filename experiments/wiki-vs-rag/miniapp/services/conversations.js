const STORAGE_KEY = 'plain-cookie-coach-conversations-v1';
const LEGACY_STORAGE_KEY = 'jing-coach-conversations-v1';
const MAX_CONVERSATIONS = 20;

function list() {
  try {
    const current = wx.getStorageSync(STORAGE_KEY);
    if (Array.isArray(current)) return current;
    const legacy = wx.getStorageSync(LEGACY_STORAGE_KEY);
    if (Array.isArray(legacy)) {
      wx.setStorageSync(STORAGE_KEY, legacy);
      return legacy;
    }
    return [];
  } catch (error) {
    return [];
  }
}

function persist(items) {
  wx.setStorageSync(STORAGE_KEY, items.slice(0, MAX_CONVERSATIONS));
}

function titleFromMessages(messages) {
  const firstUser = (messages || []).find((item) => item.role === 'user');
  const text = firstUser ? String(firstUser.text || '') : '新的复盘';
  return text.length > 26 ? `${text.slice(0, 26)}…` : text;
}

function save(conversation) {
  const items = list().filter((item) => item.id !== conversation.id);
  const next = {
    ...conversation,
    messages: (conversation.messages || []).slice(-24),
    title: conversation.title || titleFromMessages(conversation.messages),
    updatedAt: Date.now(),
  };
  persist([next, ...items]);
  return next;
}

function remove(id) {
  const items = list();
  const removed = items.find((item) => item.id === id) || null;
  persist(items.filter((item) => item.id !== id));
  return removed;
}

function restore(conversation) {
  if (!conversation) return;
  const items = list().filter((item) => item.id !== conversation.id);
  persist([conversation, ...items]);
}

module.exports = { list, remove, restore, save };
