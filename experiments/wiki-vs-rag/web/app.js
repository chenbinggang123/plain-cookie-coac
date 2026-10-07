const $ = (selector) => document.querySelector(selector);
const state = { result: null };

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || `请求失败：${response.status}`);
  return payload.data;
}

function providerConfig(prefix) {
  return {
    kind: $(`#${prefix}Kind`).value,
    base_url: $(`#${prefix}Base`).value.trim(),
    model: $(`#${prefix}Model`).value.trim(),
    api_key: $(`#${prefix}Key`).value.trim(),
  };
}

function agentSettings() {
  return {
    max_rounds: Number($("#maxRounds").value),
    semantic_top_k: Number($("#semanticTopK").value),
    wiki_max_hops: 1,
    wiki_max_nodes: Number($("#wikiNodes").value),
    final_evidence: Number($("#finalEvidence").value),
    token_budget: Number($("#tokenBudget").value),
    answer_max_chars: Number($("#answerChars").value),
  };
}

function showNotice(message, kind = "") {
  const notice = $("#notice");
  notice.textContent = message;
  notice.className = `notice ${kind}`;
  notice.hidden = !message;
}

function validateRunConfiguration() {
  const embedding = providerConfig("embedding");
  const generation = providerConfig("generation");
  if (!embedding.base_url || !embedding.model) {
    throw new Error("请先在下方设置中填写 Embedding 服务地址和模型名。");
  }
  if (!generation.base_url || !generation.model) {
    throw new Error("请先在下方设置中填写回答模型地址和模型名。");
  }
  if (generation.kind === "openai" && /api\.deepseek\.com/i.test(generation.base_url) && !generation.api_key) {
    const settings = $(".settings-panel");
    settings.open = true;
    $("#generationKey").focus();
    throw new Error("还缺 DeepSeek API Key。请在已展开的“模型、索引与预算设置”中填写密钥，再点击分析；密钥不会写入本地文件。");
  }
  return { embedding, generation };
}

function actionableRunError(error) {
  const message = error?.message || String(error);
  if (/回答生成阶段失败/.test(message)) {
    $(".settings-panel").open = true;
    return `DeepSeek 回答服务连接失败。Embedding 检索已经通过，请检查网络、代理或生成服务地址后重试。\n技术信息：${message}`;
  }
  if (/Embedding 检索阶段失败/.test(message)) {
    $(".settings-panel").open = true;
    return `本地 Embedding 服务没有响应。请确认 Ollama 正在运行，并保持地址为 http://127.0.0.1:11434；服务恢复后可直接重试。\n技术信息：${message}`;
  }
  if (/WinError 10061|actively refused|积极拒绝/i.test(message)) {
    const settings = $(".settings-panel");
    settings.open = true;
    return `模型服务连接被拒绝。请检查下方 Embedding 与回答模型地址。\n技术信息：${message}`;
  }
  if (/HTTP 401|unauthorized|authentication/i.test(message)) {
    $(".settings-panel").open = true;
    $("#generationKey").focus();
    return "回答模型鉴权失败。请检查 DeepSeek API Key 后重试。";
  }
  return message;
}

function setBusy(button, busy, busyText) {
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
  }
}

async function refreshStatus() {
  try {
    const data = await api("/api/status");
    const ready = data.index_ready && !data.index_stale;
    $("#statusDot").className = `status-dot ${ready ? "ready" : ""}`;
    $("#statusTitle").textContent = ready ? "教练已就绪" : data.index_ready ? "知识库有更新" : "需要创建索引";
    $("#statusDetail").textContent = `${data.file_count} 个文档，${data.live_chunk_count} 个知识片段`;
    const chips = $("#questionChips");
    chips.replaceChildren();
    data.sample_questions.forEach((question) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "question-chip";
      button.textContent = question;
      button.addEventListener("click", () => { $("#question").value = question; $("#question").focus(); });
      chips.append(button);
    });
  } catch (error) {
    $("#statusDot").className = "status-dot error";
    $("#statusTitle").textContent = "无法读取知识库";
    $("#statusDetail").textContent = error.message;
  }
}

function levelText(level) {
  return { 1: "L1 入门执行型", 2: "L2 条件判断型", 3: "L3 权衡复盘型" }[level] || `L${level}`;
}

async function refreshProfile() {
  const user = encodeURIComponent($("#userId").value.trim() || "local-user");
  const hero = encodeURIComponent($("#hero").value.trim() || "镜");
  try {
    const profile = await api(`/api/profile?user_id=${user}&hero=${hero}`);
    renderProfile(profile);
  } catch (error) {
    showNotice(error.message, "error");
  }
}

function renderProfile(profile) {
  const target = $("#profileDimensions");
  target.replaceChildren();
  Object.entries(profile.dimensions).forEach(([key, item]) => {
    const section = document.createElement("section");
    section.className = "dimension-card";
    const confidence = Math.round((item.confidence || 0) * 100);
    section.innerHTML = `<div><strong>${item.label}</strong><small>${item.description}</small></div><span>${levelText(item.level)}</span><p>置信度 ${confidence}%</p>`;
    const controls = document.createElement("div");
    controls.className = "level-buttons";
    [1, 2, 3].forEach((level) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `L${level}`;
      button.className = item.level === level ? "active" : "";
      button.addEventListener("click", async () => {
        const updated = await api("/api/profile", {
          method: "POST",
          body: JSON.stringify({ user_id: profile.user_id, hero: profile.hero, dimension: key, level }),
        });
        renderProfile(updated);
      });
      controls.append(button);
    });
    section.append(controls);
    target.append(section);
  });
}

function estimateCost(usage) {
  if (!usage?.available) return null;
  const input = Number(usage.input_tokens) || 0;
  const output = Number(usage.output_tokens) || 0;
  const cached = Math.min(input, Number(usage.cached_tokens) || 0);
  const uncached = Math.max(0, input - cached);
  return (
    cached * (Number($("#priceCacheHit").value) || 0) +
    uncached * (Number($("#priceCacheMiss").value) || 0) +
    output * (Number($("#priceOutput").value) || 0)
  ) / 1_000_000;
}

function renderResult(result) {
  state.result = result;
  const personal = result.personalization || {};
  const usage = result.generation?.token_usage || {};
  const toolCalls = result.trace?.tool_calls || [];
  const embeddingCalls = toolCalls.filter((call) => call.tool === "semantic_search").length;
  const cost = estimateCost(usage);
  const levelSource = {
    question_power: `问题中的战力 ${Number(personal.declared_power || 0).toLocaleString()}`,
    manual_override: "本次手动指定",
    profile: "历史画像",
  }[personal.level_source] || "当前画像";
  $("#levelBadge").textContent = `${personal.dimension_label || "局面决策"} · ${personal.level_label || "L2"} · ${levelSource}`;
  $("#answerCopy").textContent = result.answer || "知识库没有形成可用回答。";
  const tokenText = usage.available ? `${Number(usage.total_tokens).toLocaleString()} Token` : "Token 未返回";
  $("#answerMeta").textContent = `检索 ${result.retrieval_ms} ms｜生成 ${result.generation_ms || 0} ms｜生成 API 1 次｜Embedding ${embeddingCalls} 次｜${tokenText}${cost == null ? "" : `｜约 $${cost.toFixed(6)}`}`;
  $("#answerCard").hidden = false;
  $("#evidencePanel").hidden = false;
  renderTrace(result);
  renderEvidence(result.results || []);
  $("#answerCard").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderTrace(result) {
  const trace = result.trace || {};
  const audit = result.audit || {};
  const plan = result.plan || {};
  const contract = plan.teaching_contract || {};
  const cells = [
    ["路由", result.route || "未知"],
    ["检索轮次", trace.rounds || 0],
    ["最终证据", (result.results || []).length],
    ["证据审查", audit.decision || "INSUFFICIENT"],
    ["Wiki 新增", trace.wiki_added_evidence || 0],
  ];
  const grid = $("#traceGrid");
  grid.replaceChildren();
  cells.forEach(([label, value]) => {
    const cell = document.createElement("div");
    cell.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    grid.append(cell);
  });
  const structure = (contract.structure || []).join(" → ");
  const missing = audit.missing_dimensions || audit.missing_conditions || [];
  $("#traceDetails").textContent = `教学目标：${contract.learning_goal || "未记录"}\n建议重点（不是固定目录）：${structure || "未记录"}\nWiki 新增条件：${trace.wiki_added_required_conditions || 0}\n仍缺少：${missing.length ? missing.join("、") : "无必需缺口"}`;
}

function renderEvidence(items) {
  const target = $("#evidenceList");
  target.replaceChildren();
  items.forEach((item, index) => {
    const fragment = $("#evidenceTemplate").content.cloneNode(true);
    fragment.querySelector(".evidence-rank").textContent = String(index + 1).padStart(2, "0");
    fragment.querySelector("strong").textContent = item.document_title || item.heading || "未命名证据";
    fragment.querySelector("small").textContent = item.source_path || "";
    fragment.querySelector("em").textContent = Number(item.score || 0).toFixed(3);
    fragment.querySelector(".evidence-reason").textContent = item.selection_reason || item.heading || "";
    fragment.querySelector(".evidence-content").textContent = item.content || "";
    target.append(fragment);
  });
}

$("#runButton").addEventListener("click", async () => {
  const question = $("#question").value.trim();
  if (!question) { showNotice("请先描述一个真实对局问题。", "error"); return; }
  const button = $("#runButton");
  showNotice("");
  try {
    const providers = validateRunConfiguration();
    setBusy(button, true, "正在分析局面…");
    showNotice("正在检索知识库并规划回答，请稍候…", "progress");
    const declared = $("#declaredLevel").value;
    const result = await api("/api/coach/run", {
      method: "POST",
      body: JSON.stringify({
        question,
        user_id: $("#userId").value.trim() || "local-user",
        hero: $("#hero").value.trim() || "镜",
        declared_level: declared === "auto" ? null : Number(declared),
        settings: agentSettings(),
        embedding: providers.embedding,
        generation: providers.generation,
      }),
    });
    showNotice("");
    renderResult(result);
    await refreshProfile();
  } catch (error) {
    showNotice(actionableRunError(error), "error");
  } finally {
    setBusy(button, false);
  }
});

$("#feedbackPanel").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-feedback]");
  if (!button || !state.result) return;
  const personal = state.result.personalization || {};
  try {
    const data = await api("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        run_id: state.result.run_id,
        user_id: personal.user_id,
        hero: personal.hero,
        dimension: personal.dimension,
        feedback: button.dataset.feedback,
      }),
    });
    renderProfile(data.profile);
    showNotice(data.message, "success");
  } catch (error) {
    showNotice(error.message, "error");
  }
});

$("#indexButton").addEventListener("click", async () => {
  const button = $("#indexButton");
  setBusy(button, true, "正在建立索引…");
  try {
    const data = await api("/api/index", { method: "POST", body: JSON.stringify({ embedding: providerConfig("embedding") }) });
    showNotice(`索引完成：${data.file_count} 个文件，${data.chunk_count} 个片段，用时 ${data.elapsed_ms} ms。`, "success");
    await refreshStatus();
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    setBusy(button, false);
  }
});

$("#userId").addEventListener("change", refreshProfile);
$("#hero").addEventListener("change", refreshProfile);
refreshStatus();
refreshProfile();
