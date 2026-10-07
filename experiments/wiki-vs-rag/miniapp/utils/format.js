const LEVEL_LABELS = {
  1: 'L1 入门执行型',
  2: 'L2 条件判断型',
  3: 'L3 权衡复盘型',
};

const LEVEL_SOURCE_LABELS = {
  question_power: '问题中的战力判断',
  manual_override: '本次手动指定',
  profile: '历史画像',
};

function levelLabel(level) {
  return LEVEL_LABELS[Number(level)] || `L${level || 2}`;
}

function levelSourceLabel(source) {
  return LEVEL_SOURCE_LABELS[source] || '自动匹配';
}

function formatTime(timestamp) {
  const date = timestamp ? new Date(timestamp) : new Date();
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  if (sameDay) return `今天 ${hours}:${minutes}`;
  return `${date.getMonth() + 1}月${date.getDate()}日 ${hours}:${minutes}`;
}

function splitInline(text) {
  return String(text || '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .trim();
}

function formatAnswer(answer) {
  const lines = String(answer || '').replace(/\r/g, '').split('\n');
  const blocks = [];
  let paragraph = [];
  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push({ type: 'paragraph', text: splitInline(paragraph.join('\n')) });
    paragraph = [];
  };
  lines.forEach((raw) => {
    const line = raw.trim();
    if (!line) {
      flushParagraph();
      return;
    }
    const heading = line.match(/^#{1,3}\s+(.+)/);
    const ordered = line.match(/^(\d+)[.、]\s*(.+)/);
    const bullet = line.match(/^[-*•]\s+(.+)/);
    if (heading) {
      flushParagraph();
      blocks.push({ type: 'heading', text: splitInline(heading[1]) });
    } else if (ordered) {
      flushParagraph();
      blocks.push({ type: 'ordered', marker: ordered[1], text: splitInline(ordered[2]) });
    } else if (bullet) {
      flushParagraph();
      blocks.push({ type: 'bullet', marker: '·', text: splitInline(bullet[1]) });
    } else {
      paragraph.push(line);
    }
  });
  flushParagraph();
  return blocks.length ? blocks : [{ type: 'paragraph', text: '暂时没有可展示的回答。' }];
}

function normalizeEvidence(items) {
  return (items || []).map((item, index) => ({
    ...item,
    rank: String(index + 1).padStart(2, '0'),
    title: item.document_title || item.heading || '未命名知识条目',
    path: item.source_path || '本地知识库',
    scoreText: Number(item.score || 0).toFixed(3),
    reason: item.selection_reason || item.heading || '与当前问题相关',
    content: item.content || '没有可展示的证据摘要。',
    open: false,
  }));
}

function buildCoachMessage(result) {
  const personalization = result.personalization || {};
  const audit = result.audit || {};
  const trace = result.trace || {};
  const plan = result.plan || {};
  const contract = plan.teaching_contract || {};
  const missing = audit.missing_dimensions || audit.missing_conditions || [];
  const evidence = normalizeEvidence(result.results || result.evidence || []);
  return {
    id: `coach-${result.run_id || Date.now()}`,
    role: 'coach',
    createdAt: Date.now(),
    runId: result.run_id || '',
    answer: result.answer || '知识库没有形成可用回答。',
    blocks: formatAnswer(result.answer),
    dimension: personalization.dimension || 'decision',
    dimensionLabel: personalization.dimension_label || '局面决策',
    level: Number(personalization.level || 2),
    levelLabel: personalization.level_label || levelLabel(personalization.level),
    levelSource: levelSourceLabel(personalization.level_source),
    userId: personalization.user_id || 'local-user',
    hero: personalization.hero || '全英雄',
    evidence,
    evidenceInsufficient: !evidence.length || ['ASK_USER', 'INSUFFICIENT'].includes(audit.decision),
    rationale: {
      route: result.route || '未知',
      learningGoal: contract.learning_goal || personalization.learning_goal || '根据当前水平给出下一步判断依据',
      rounds: trace.rounds || 0,
      evidenceCount: evidence.length,
      wikiAdded: trace.wiki_added_evidence || 0,
      missingText: missing.length ? missing.join('、') : '暂无必需缺口',
    },
    feedbackState: 'idle',
    feedbackMessage: '',
  };
}

module.exports = {
  buildCoachMessage,
  formatAnswer,
  formatTime,
  levelLabel,
  levelSourceLabel,
};
