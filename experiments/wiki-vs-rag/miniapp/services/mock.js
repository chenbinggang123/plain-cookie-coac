const DEFAULT_QUESTIONS = [
  '李白逆风时应该怎么找翻盘点？',
  '貂蝉四级第一波没抓到人，下一步做什么？',
  '对面中辅一直跟野区，打野该怎么发育？',
  '我玩射手经济第一，团战为什么总是暴毙？',
];

const PROFILE = {
  user_id: 'local-user',
  hero: '全英雄',
  dimensions: {
    mechanics: { label: '操作与连招', description: '技能衔接、走位、连招与操作稳定性', level: 2, level_label: 'L2 条件判断型', confidence: 0.72 },
    economy: { label: '发育与资源', description: '刷野、兵线、经济与资源转换', level: 2, level_label: 'L2 条件判断型', confidence: 0.58 },
    decision: { label: '局面决策', description: '入侵、抓边、接团、撤退与风险判断', level: 2, level_label: 'L2 条件判断型', confidence: 0.64 },
  },
};

function wait(ms = 520) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

async function status(scenario) {
  await wait(220);
  if (scenario === 'offline') throw Object.assign(new Error('当前网络不可用，请检查连接后重试。'), { type: 'offline' });
  if (scenario === 'service_unavailable') throw Object.assign(new Error('教练服务暂时不可用，请稍后重试。'), { type: 'service' });
  return {
    file_count: 184,
    live_chunk_count: 1267,
    index_ready: scenario !== 'index_missing',
    index_stale: scenario === 'index_stale',
    sample_questions: DEFAULT_QUESTIONS,
    agent: '水平感知规划式 Agent（Wiki 开启）',
  };
}

async function profile(userId, hero, scenario) {
  await wait(300);
  if (scenario === 'profile_error') throw Object.assign(new Error('能力画像暂时没有加载成功，请点击重试。'), { type: 'profile' });
  const value = clone(PROFILE);
  value.user_id = userId || 'local-user';
  value.hero = hero || '全英雄';
  return value;
}

async function setProfile(payload) {
  await wait(360);
  if (PROFILE.dimensions[payload.dimension]) {
    PROFILE.dimensions[payload.dimension].level = Number(payload.level);
    PROFILE.dimensions[payload.dimension].level_label = `L${payload.level} ${payload.level === 1 ? '入门执行型' : payload.level === 2 ? '条件判断型' : '权衡复盘型'}`;
    PROFILE.dimensions[payload.dimension].confidence = Math.max(PROFILE.dimensions[payload.dimension].confidence, 0.7);
  }
  const value = clone(PROFILE);
  value.user_id = payload.user_id || 'local-user';
  value.hero = payload.hero || '全英雄';
  return value;
}

async function coachRun(payload, scenario) {
  await wait(1250);
  if (scenario === 'request_error') throw Object.assign(new Error('这次分析没有完成。你的问题已保留，可以直接重试。'), { type: 'server' });
  const level = Number(payload.declared_level || 2);
  const noEvidence = scenario === 'no_evidence';
  const labels = { 1: 'L1 入门执行型', 2: 'L2 条件判断型', 3: 'L3 权衡复盘型' };
  return {
    run_id: `mock-${Date.now()}`,
    answer: noEvidence
      ? '目前证据不足，不能直接判断你该不该进场。\n\n请补充两个信息：开团前敌方关键控制是否交过，以及你进场时一技能和大招是否都可用。'
      : '## 先给结论\n这局不要把“经济第一”理解成必须第一个进场。高经济核心位更应该等第一轮控制交掉，再从安全角度进入战场。\n\n## 进场前看三个条件\n1. 敌方关键硬控是否已经交出。没有看到张良大招、东皇大招这类技能时，先保留自己的关键位移。\n2. 你的退路是否还在。位移、闪现、兵线或队友至少要留一个，避免打完第一套后只能原地承伤。\n3. 队友是否能跟上第二拍。你先手但队友隔着一整个身位，经济优势会变成最高价值的阵亡。\n\n## 下一局只练一个动作\n团战爆发后先数“一、二”，确认第一轮控制和位移已经交换，再选择输出角度。复盘时只记录：我进场前看到了哪两个安全信号？',
    route: 'targeted',
    personalization: {
      user_id: payload.user_id || 'local-user',
      hero: payload.hero || '全英雄',
      dimension: 'decision',
      dimension_label: '局面决策',
      level,
      level_label: labels[level],
      level_source: payload.declared_level ? 'manual_override' : 'profile',
      learning_goal: level === 1 ? '先知道现在做什么' : level === 2 ? '学习组合条件和否决信号' : '比较机会成本与反事实选择',
    },
    plan: {
      teaching_contract: {
        learning_goal: level === 1 ? '建立可重复的进场动作' : '用安全信号替代“有经济就能进”的直觉',
      },
    },
    audit: {
      decision: noEvidence ? 'ASK_USER' : 'READY',
      missing_conditions: noEvidence ? ['敌方关键控制状态', '自身技能状态'] : [],
    },
    trace: { rounds: noEvidence ? 2 : 1, wiki_added_evidence: noEvidence ? 0 : 2 },
    results: noEvidence ? [] : [
      {
        document_title: '核心位团战进场条件与退路设计',
        source_path: '王者荣耀/团战/进场判断.md',
        score: 0.892,
        selection_reason: '同时覆盖进场时机、关键控制与退路条件',
        content: '核心位的经济优势需要通过持续存活兑现。第一轮控制未交、退路未建立时，先手进入人群会放大阵亡成本。',
      },
      {
        document_title: '高经济打野的机会成本',
        source_path: '全局决策/经济领先/核心位生存.md',
        score: 0.814,
        selection_reason: '解释了高经济位阵亡为何会影响资源节奏',
        content: '核心位阵亡不仅损失赏金，还会让接下来一轮主宰、暴君与兵线转换失去主动权。',
      },
    ],
  };
}

async function feedback(payload, scenario) {
  await wait(520);
  if (scenario === 'feedback_error') throw Object.assign(new Error('反馈暂时没有提交成功，请再试一次。'), { type: 'server' });
  return {
    message: '已记录。连续两次相同反馈后，会调整你的局面决策等级。',
    profile: clone(PROFILE),
    event: { ...payload, created_at: new Date().toISOString() },
  };
}

async function buildIndex() {
  await wait(900);
  return { file_count: 184, chunk_count: 1267, elapsed_ms: 900 };
}

module.exports = { buildIndex, coachRun, feedback, profile, setProfile, status };
