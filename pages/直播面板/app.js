const state = {
  overview: null,
  memory: null,
  configSchema: {},
  configGroups: [],
  configValues: {},
  configDirty: false,
  configFallback: false,
  dynamicOptions: {
    externalTts: [],
    externalTtsAll: [],
    ttsStats: null,
    ttsMethods: [],
    vtsCandidates: [],
    selectedTool: "",
    vtsScanning: false,
    ttsRefreshing: false,
  },
  viewerFilter: "",
  soullink: null,
  soullinkEmotion: "happy",
  soullinkParameters: null,
  soullinkMapping: null,
  soullinkMappingDraft: null,
  soullinkMappingDirty: false,
  soullinkMappingPreviewing: false,
  soullinkMappingPreviewTimer: null,
  soullinkMappingRequest: 0,
  gazeStatusLoading: false,
};

const SOULLINK_COMPOSITE_LABELS = {
  bodyXMix: "身体 X 混合",
  bodyYMix: "身体 Y 混合",
  bodyZMix: "身体 Z 混合",
  eyeSquintMix: "眯眼压低",
  mouthNeutral: "嘴角源中性",
  mouthFrownMix: "下压嘴角混合",
  browInnerMix: "内眉混合",
  browOuterMix: "外眉混合",
  browDownMix: "压眉混合",
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  [
    "subtitle", "stats", "refreshBtn", "startBtn", "stopBtn", "liveBadge",
    "liveFlow", "autoReplyPanel", "stagePanel", "topViewers", "memoryRefreshBtn",
    "memoryOverview", "memoryItems", "highlightItems", "topicItems", "threadItems",
    "summaryItems", "viewerFilter", "viewerRows", "eventCount", "eventRows",
    "configEditor", "saveConfigBtn", "resetConfigBtn", "configDirtyBadge",
    "configStatus", "obsRefreshBtn", "obsControlPanel", "toast",
    "soullinkSummary", "soullinkBadge", "soullinkStartBtn", "soullinkStopBtn",
    "soullinkResetBtn", "soullinkState", "soullinkEmotion", "soullinkVariant",
    "soullinkCharacterStage", "soullinkCharacterVisual", "soullinkRuntimeMetrics",
    "soullinkVtsNotice",
    "live2dImportBtn", "live2dRemoveBtn", "live2dFolderInput", "live2dCanvasHost",
    "live2dModelStatus", "live2dZoomControls", "live2dZoomOutBtn",
    "live2dZoomSlider", "live2dZoomInBtn", "live2dZoomValue", "live2dZoomResetBtn",
    "soullinkStyle", "soullinkPresets", "soullinkIntensity", "soullinkIntensityValue",
    "soullinkValence", "soullinkValenceValue", "soullinkArousal",
    "soullinkArousalValue", "soullinkDominance", "soullinkDominanceValue",
    "soullinkTriggerBtn", "soullinkVadMeters", "soullinkFacsMeters",
    "soullinkParamsBtn", "soullinkParameterRows", "soullinkModelParameters",
    "soullinkMappingBtn", "soullinkMappingWorkbench", "soullinkMappingMode",
    "soullinkMappingModel", "soullinkMappingStatus", "soullinkMappingValidation",
    "soullinkMappingCaptureBtn", "soullinkMappingAddBtn", "soullinkMappingResetBtn",
    "soullinkMappingDiscardBtn", "soullinkMappingSaveBtn", "soullinkMappingCloseBtn",
    "soullinkCompositeFields", "soullinkMappingRules", "soullinkMappingJson",
    "soullinkMappingImportBtn", "soullinkMappingCopyBtn", "soullinkVtsInputOptions",
    "gazeStatus", "gazeStage", "gazeDot", "gazeCoords", "gazeToggle",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });

  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });
  els.refreshBtn?.addEventListener("click", () => loadAll());
  els.memoryRefreshBtn?.addEventListener("click", () => loadMemory());
  els.startBtn?.addEventListener("click", () => startLive());
  els.stopBtn?.addEventListener("click", () => stopLive());
  els.obsRefreshBtn?.addEventListener("click", () => refreshObsControl());
  els.obsControlPanel?.addEventListener("click", handleObsControlClick);
  els.saveConfigBtn?.addEventListener("click", () => saveConfig());
  els.resetConfigBtn?.addEventListener("click", () => resetConfigForm());
  els.soullinkStartBtn?.addEventListener("click", () => controlSoullink("start"));
  els.soullinkStopBtn?.addEventListener("click", () => controlSoullink("stop"));
  els.soullinkResetBtn?.addEventListener("click", () => controlSoullink("reset"));
  els.soullinkTriggerBtn?.addEventListener("click", () => triggerSoullink());
  els.gazeToggle?.addEventListener("change", () => toggleGaze());
  els.soullinkParamsBtn?.addEventListener("click", () => loadSoullinkParameters());
  els.soullinkMappingBtn?.addEventListener("click", () => openSoullinkMapping());
  els.soullinkMappingCloseBtn?.addEventListener("click", () => closeSoullinkMapping());
  els.soullinkMappingAddBtn?.addEventListener("click", addSoullinkMappingRule);
  els.soullinkMappingCaptureBtn?.addEventListener("click", captureSoullinkMappingNeutral);
  els.soullinkMappingResetBtn?.addEventListener("click", resetSoullinkMapping);
  els.soullinkMappingDiscardBtn?.addEventListener("click", discardSoullinkMappingPreview);
  els.soullinkMappingSaveBtn?.addEventListener("click", saveSoullinkMapping);
  els.soullinkMappingImportBtn?.addEventListener("click", importSoullinkMappingJson);
  els.soullinkMappingCopyBtn?.addEventListener("click", copySoullinkMappingJson);
  els.soullinkMappingRules?.addEventListener("input", handleSoullinkMappingInput);
  els.soullinkMappingRules?.addEventListener("change", handleSoullinkMappingInput);
  els.soullinkMappingRules?.addEventListener("click", handleSoullinkMappingClick);
  els.soullinkCompositeFields?.addEventListener("input", handleSoullinkCompositeInput);
  els.configEditor?.addEventListener("click", (event) => {
    if (!event.target.closest("[data-open-soullink-mapping]")) return;
    activateTab("soullink");
    openSoullinkMapping();
  });
  els.soullinkStyle?.addEventListener("change", () => {
    controlSoullink("configure", { style: els.soullinkStyle.value });
  });
  els.soullinkPresets?.addEventListener("click", handleSoullinkPreset);
  els.live2dImportBtn?.addEventListener("click", () => els.live2dFolderInput?.click());
  els.live2dRemoveBtn?.addEventListener("click", () => window.Live2DPreview?.removeModel());
  els.live2dFolderInput?.addEventListener("change", importLive2DModel);
  els.live2dZoomOutBtn?.addEventListener("click", () => window.Live2DPreview?.zoomBy(-0.1));
  els.live2dZoomInBtn?.addEventListener("click", () => window.Live2DPreview?.zoomBy(0.1));
  els.live2dZoomResetBtn?.addEventListener("click", () => window.Live2DPreview?.resetZoom());
  els.live2dZoomSlider?.addEventListener("input", () => {
    window.Live2DPreview?.setZoom(Number(els.live2dZoomSlider.value || 100) / 100);
  });
  [
    els.soullinkIntensity, els.soullinkValence, els.soullinkArousal, els.soullinkDominance,
  ].forEach((control) => control?.addEventListener("input", updateSoullinkControlValues));
  els.viewerFilter?.addEventListener("input", () => {
    state.viewerFilter = els.viewerFilter.value.trim().toLowerCase();
    renderViewers();
  });

  loadAll();
  window.setInterval(loadAll, 15000);
  window.setInterval(() => {
    if (document.getElementById("panel-soullink")?.classList.contains("is-active")) {
      loadSoullink({ silent: true });
    }
  }, 500);
  window.setInterval(() => {
    if (!els.soullinkMappingWorkbench?.hidden && state.soullinkMappingDirty) {
      previewSoullinkMapping({ silent: true });
    }
  }, 60000);
  updateSoullinkControlValues();
  window.Live2DPreview?.init({
    host: els.live2dCanvasHost,
    fallback: els.soullinkCharacterVisual,
    onStatus: renderLive2DModelStatus,
    onZoomChange: renderLive2DZoom,
  });
});

function activateTab(tab) {
  document.querySelectorAll(".tab").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.tab === tab);
  });
  document.querySelectorAll(".panel").forEach((item) => {
    item.classList.toggle("is-active", item.id === `panel-${tab}`);
  });
  if (tab === "memory" && !state.memory) {
    loadMemory();
  }
  if (tab === "config" && !Object.keys(state.configSchema).length) {
    loadConfig();
  }
  if (tab === "soullink") {
    loadSoullink();
  }
}

async function loadAll() {
  try {
    const [overview] = await Promise.all([
      LivePageApi.get("/overview"),
      loadConfig({ silent: true }),
      loadDynamicOptions({ silent: true }),
    ]);
    state.overview = overview;
    renderOverview();
    if (document.getElementById("panel-memory")?.classList.contains("is-active")) {
      await loadMemory();
    }
  } catch (error) {
    renderOfflineShell(error);
    showToast(error.message || String(error));
  }
}

async function loadMemory() {
  try {
    const data = await LivePageApi.get("/memory");
    state.memory = data;
    renderMemory();
    renderViewers();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function loadConfig(options = {}) {
  if (state.configDirty && options.silent) return null;
  try {
    const data = await LivePageApi.get("/config/schema");
    applyConfigModel({
      schema: data.schema || {},
      groups: data.groups || [],
      values: data.values || {},
      fallback: false,
    });
    state.configDirty = false;
    return data;
  } catch (error) {
    useFallbackConfigModel();
    if (!options.silent) showToast(error.message || String(error));
    return null;
  }
}

function applyConfigModel({ schema, groups, values, fallback }) {
  state.configSchema = schema;
  state.configGroups = groups;
  state.configValues = { ...LiveConfigForm.defaultValues(schema), ...values };
  state.configFallback = Boolean(fallback);
  renderConfig();
  updateDirtyState();
}

function useFallbackConfigModel() {
  if (Object.keys(state.configSchema).length) return;
  applyConfigModel({
    schema: FALLBACK_CONFIG_SCHEMA,
    groups: FALLBACK_CONFIG_GROUPS,
    values: state.overview?.config || {},
    fallback: true,
  });
}

async function startLive() {
  try {
    const formValues = collectConfigValues();
    const roomId = formValues.bilibili_room_id
      || state.overview?.live?.room_id
      || state.overview?.config?.bilibili_room_id
      || 0;
    const data = await LivePageApi.post("/control/start", { room_id: roomId });
    showToast(data.message || "已请求启动监听。");
    await loadAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function stopLive() {
  try {
    const data = await LivePageApi.post("/control/stop", {});
    showToast(data.message || "已请求停止监听。");
    await loadAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function saveConfig() {
  try {
    const values = collectConfigValues();
    els.saveConfigBtn.disabled = true;
    const data = await LivePageApi.post("/config/save", { values });
    state.configValues = data.values || values;
    state.configDirty = false;
    renderConfig();
    updateDirtyState();
    showToast(data.message || "配置已保存。");
    await loadAll();
  } catch (error) {
    if (state.configFallback) {
      showToast("当前 AstrBot 进程还没加载拓展页保存接口，重启/重载插件后即可保存。");
    } else {
      showToast(error.message || String(error));
    }
  } finally {
    els.saveConfigBtn.disabled = false;
  }
}

function resetConfigForm() {
  state.configDirty = false;
  renderConfig();
  updateDirtyState();
}


function renderOverview() {
  const data = state.overview || {};
  const live = data.live || {};
  const twitch = data.twitch || {};
  const memory = data.memory || {};
  const autoReply = data.auto_reply || {};
  const companion = data.companion || {};
  const integration = data.integration || {};
  const streamer = autoReply.streamer || {};
  if (state.configFallback && !state.configDirty && data.config) {
    state.configValues = { ...state.configValues, ...data.config };
    renderConfig();
  }
  const anyRunning = Boolean(live.running || twitch.running);
  els.subtitle.textContent = [
    `B站：${live.running ? `监听中（${live.room_id || "未配置房间"}）` : "未运行"}`,
    `Twitch：${twitch.connected ? `已连接（${twitch.channel || "未配置频道"}）` : (twitch.running ? "重连中" : "未运行")}`,
  ].join(" · ");
  els.liveBadge.textContent = anyRunning ? "监听中" : "未运行";
  els.liveBadge.className = `badge ${anyRunning ? "ok" : "idle"}`;

  renderStats([
    ["直播事件", (live.session_count || 0) + (twitch.cache_count || 0), "B站本场 + Twitch 缓存"],
    ["缓存事件", (live.cache_count || 0) + (twitch.cache_count || 0), "两平台最近保留"],
    ["直播记忆", memory.memory_count || 0, "可承接条目"],
    ["观众画像", data.viewers?.count || 0, "累计观众"],
    ["本分钟回复", `${autoReply.used_this_minute || 0}/${autoReply.max_per_minute || 0}`, "普通弹幕限流"],
    ["直播小结", memory.summary_count || 0, "历史整理"],
    ["联动健康", `${integration.ok_count || 0}/${integration.total || 0}`, "监听/字幕/记忆"],
  ]);

  renderLiveFlow(data);
  renderMetricList(els.autoReplyPanel, [
    ["状态", boolText(autoReply.enabled)],
    ["模式", autoReply.mode || "native"],
    ["身份", autoReply.identity_label || autoReply.identity_mode || "主播模式"],
    ["主播称呼", streamer.name || "主播"],
    ["身份来源", streamer.source || "fallback"],
    ["待回应事件", autoReply.pending || 0],
    ["冷却", `${autoReply.cooldown_seconds || 0}s`],
    ["跳过表情/语音", boolText(autoReply.skip_rich_danmaku)],
    ["读空气降噪", boolText(autoReply.air_guard)],
    ["陪伴读空气", boolText(autoReply.air_guard_model)],
    ["回应阈值", autoReply.air_guard_threshold || 2.5],
    ["全量 TTS", boolText(autoReply.force_full_tts)],
    ["TTS/打字机同步", boolText(autoReply.sync_tts_subtitle)],
    ["TTS 本机播放", boolText(autoReply.local_playback)],
    ["每分钟上限", autoReply.max_per_minute === 0 ? "不限" : autoReply.max_per_minute],
    ["豁免事件", (autoReply.exempt_event_types || []).join("、") || "无"],
    ["Twitch 监听", twitch.connected ? "已连接（只读）" : (twitch.running ? "重连中" : "未运行")],
    ["Twitch 频道", twitch.channel || "未配置"],
    ["Twitch 自动回应", boolText(twitch.auto_reply_enabled)],
    ["Twitch 待回应", twitch.pending || 0],
  ]);
  renderMetricList(els.stagePanel, [
    ["VTS", data.vts?.connected ? "已连接" : "未连接"],
    ["VTS 地址", data.vts?.url || "--"],
    ["Soullink", data.soullink?.running ? "运行中" : (data.soullink?.enabled ? "已启用" : "未启用")],
    ["情绪模式", data.soullink?.mode || "emotion"],
    ["动作风格", data.soullink?.style || "natural"],
    ["字幕", data.subtitle?.enabled ? (data.subtitle.running ? "运行中" : "已启用") : "未启用"],
    ["字幕地址", data.subtitle?.url || "--"],
    ["嘴型", data.mouth_sync?.enabled ? "已启用" : "未启用"],
    ["嘴型参数", data.mouth_sync?.parameter || "--"],
    ["陪伴插件", companion.available ? "已连接" : "未找到"],
    ["LivingMemory", data.living_memory?.ready ? "已就绪" : (data.living_memory?.available ? "初始化中" : "未找到")],
  ]);
  renderObsControl(data.obs_control || {});
  renderTopViewers(data.live?.top_viewers || []);
  renderEvents();
}

function renderOfflineShell(error) {
  useFallbackConfigModel();
  els.subtitle.textContent = "拓展页 API 暂不可用，仍可查看本地页面结构。";
  els.liveBadge.textContent = "离线";
  els.liveBadge.className = "badge idle";
  renderStats([
    ["直播事件", 0, "等待 API"],
    ["缓存事件", 0, "等待 API"],
    ["直播记忆", 0, "等待 API"],
    ["观众画像", 0, "等待 API"],
  ]);
  renderMetricList(els.autoReplyPanel, [["状态", "未知"], ["原因", error?.message || "请求失败"]]);
  renderMetricList(els.stagePanel, [["字幕预览", "页面内可用"], ["真实 overlay", "等待 API"]]);
  els.liveFlow.innerHTML = emptyText("未连接直播也可以使用配置页；当前只是拓展页 API 没有响应。");
  renderObsControl({});
  renderEvents();
}

function renderStats(items) {
  els.stats.innerHTML = items.map(([label, value, hint]) => `
    <article class="stat">
      <b>${escapeHtml(value)}</b>
      <span>${escapeHtml(label)}</span>
      <small>${escapeHtml(hint)}</small>
    </article>
  `).join("");
}

function renderLiveFlow(data) {
  const live = data.live || {};
  const twitch = data.twitch || {};
  const companion = data.companion || {};
  const memory = data.memory || {};
  const living = data.living_memory || {};
  const steps = [
    ["B站监听", live.running ? "ok" : "idle", live.running ? `${live.type}/${live.backend}` : "可在配置页准备"],
    ["Twitch 监听", twitch.connected ? "ok" : "idle", twitch.connected ? `${twitch.channel || "未配置"} · 匿名只读` : (twitch.running ? "连接重试中" : "可在配置页准备")],
    ["事件缓存", live.cache_count ? "ok" : "idle", `${live.cache_count || 0} 条`],
    ["自动回应", data.auto_reply?.enabled ? "ok" : "idle", data.auto_reply?.mode || "native"],
    ["直播记忆", memory.enabled ? "ok" : "idle", `${memory.memory_count || 0} 条记忆`],
    ["陪伴联动", companion.available ? "ok" : "idle", companion.available ? "已连接" : "未找到"],
    ["长期记忆", living.ready ? "ok" : "idle", living.ready ? `召回 top_k ${living.top_k || 0}` : (living.available ? "初始化中" : "未找到")],
    ["VTS/字幕", data.vts?.connected || data.subtitle?.running ? "ok" : "idle", data.subtitle?.running ? "字幕运行" : "演出待命"],
  ];
  els.liveFlow.innerHTML = steps.map(([title, status, desc]) => `
    <div class="flow-step ${status}">
      <span></span>
      <b>${escapeHtml(title)}</b>
      <small>${escapeHtml(desc)}</small>
    </div>
  `).join("");
}

function renderObsControl(control) {
  if (!els.obsControlPanel) return;
  const obs = control.obs || {};
  const l2d = control.l2dstudio || {};
  const settings = control.settings || {};
  const enabled = Boolean(control.enabled);
  const connected = Boolean(obs.websocket?.connected);
  const streamAllowed = Boolean(control.safety?.stream_start_allowed);
  const actionDisabled = !enabled;
  const obsActionDisabled = actionDisabled || !connected;
  const streamDisabled = obsActionDisabled || !streamAllowed;
  const cards = [
    ["控制开关", enabled ? "已启用" : "未启用", enabled ? "可执行开播控制" : "到配置页启用 OBS 开播控制", enabled ? "ok" : "idle"],
    ["OBS", obs.running ? "运行中" : "未运行", obs.configured ? (obs.process?.exists ? obs.process?.name || "路径可用" : "路径不存在") : "未配置路径", obs.running ? "ok" : "idle"],
    ["L2DStudio", l2d.running ? "运行中" : "未运行", l2d.configured ? (l2d.process?.exists ? l2d.process?.name || "路径可用" : "路径不存在") : "未配置路径", l2d.running ? "ok" : "idle"],
    ["OBS WebSocket", connected ? "已连接" : "未连接", connected ? `${obs.websocket?.obs_version || "OBS"} / ${obs.websocket?.websocket_version || "WebSocket"}` : (obs.websocket?.error || "等待 OBS 启动并开启 WebSocket"), connected ? "ok" : "idle"],
    ["当前场景", obs.current_scene || settings.obs_live_scene_name || "未读取", settings.obs_live_scene_name ? `默认：${settings.obs_live_scene_name}` : "未配置默认场景", obs.current_scene ? "ok" : "idle"],
    ["推流状态", obs.streaming ? "直播中" : "未推流", streamAllowed ? "允许二次确认开播" : "配置禁止插件开播", obs.streaming ? "danger" : "idle"],
  ];
  els.obsControlPanel.innerHTML = `
    <div class="obs-status-grid">
      ${cards.map(([label, value, note, tone]) => `
        <section class="obs-status-card ${escapeHtml(tone)}">
          <span>${escapeHtml(label)}</span>
          <b>${escapeHtml(value)}</b>
          <small>${escapeHtml(note)}</small>
        </section>
      `).join("")}
    </div>
    <div class="obs-action-grid">
      <button type="button" data-obs-action="open_obs" ${actionDisabled || !obs.configured ? "disabled" : ""}>打开 OBS</button>
      <button type="button" data-obs-action="open_l2dstudio" ${actionDisabled || !l2d.configured ? "disabled" : ""}>打开 L2DStudio</button>
      <button type="button" data-obs-action="start_apps" ${actionDisabled ? "disabled" : ""}>打开两端</button>
      <button type="button" data-obs-action="check" ${actionDisabled ? "disabled" : ""}>检查连接</button>
      <button type="button" data-obs-action="debug" ${actionDisabled ? "disabled" : ""}>直播调试</button>
      <button type="button" data-obs-action="switch_scene" ${obsActionDisabled || !settings.obs_live_scene_name ? "disabled" : ""}>切换场景</button>
      <button type="button" data-obs-action="${obs.virtual_camera ? "stop_virtual_camera" : "start_virtual_camera"}" ${obsActionDisabled ? "disabled" : ""}>${obs.virtual_camera ? "关闭虚拟摄像机" : "开启虚拟摄像机"}</button>
      <button type="button" data-obs-action="${obs.recording ? "stop_record" : "start_record"}" ${obsActionDisabled ? "disabled" : ""}>${obs.recording ? "停止录制" : "开始录制"}</button>
      <button type="button" class="danger" data-obs-action="start_stream" ${streamDisabled || obs.streaming ? "disabled" : ""}>开始直播</button>
      <button type="button" class="danger-outline" data-obs-action="stop_stream" ${obsActionDisabled || !obs.streaming ? "disabled" : ""}>停止直播</button>
    </div>
    <p class="muted obs-hint">开始直播会调用 OBS StartStream，要求配置页开启“允许插件开始推流”，并且需要二次点击确认。B 站推流侧建议先安装 obs-bilibili-stream。</p>
  `;
}

async function refreshObsControl() {
  try {
    const data = await LivePageApi.get("/control/obs/status");
    state.overview = { ...(state.overview || {}), obs_control: data };
    renderObsControl(data);
    showToast("OBS 状态已刷新。");
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function handleObsControlClick(event) {
  const button = event.target instanceof Element ? event.target.closest("[data-obs-action]") : null;
  if (!button) return;
  const action = button.dataset.obsAction || "";
  const body = { action };
  if (action === "start_stream") {
    if (!requireSecondClick(button, "start_stream", "再次点击会真正开始 OBS 推流", "确认开播")) return;
    body.confirm = true;
  }
  try {
    button.disabled = true;
    const data = await LivePageApi.post("/control/obs/action", body);
    if (data.obs_control) {
      state.overview = { ...(state.overview || {}), obs_control: data.obs_control };
      renderObsControl(data.obs_control);
    } else {
      await loadAll();
    }
    showToast(data.message || "OBS 控制动作已完成。");
  } catch (error) {
    showToast(error.message || String(error));
  } finally {
    button.disabled = false;
  }
}

function renderTopViewers(items) {
  if (!items.length) {
    els.topViewers.innerHTML = emptyText("本场还没有观众活跃数据；配置页和字幕预览无需开播也能使用。");
    return;
  }
  els.topViewers.innerHTML = items.map((item) => `
    <div class="viewer-chip">
      <b>${escapeHtml(item.name)}</b>
      <span>${escapeHtml(item.count)} 次</span>
    </div>
  `).join("");
}

function renderMemory() {
  const payload = state.memory?.memory || state.overview?.memory || {};
  els.memoryOverview.innerHTML = state.memory?.overview
    ? `<pre>${escapeHtml(state.memory.overview)}</pre>`
    : emptyText(state.memory?.message || "暂时还没有直播专用记忆。");
  renderCards(els.memoryItems, payload.recent_items || payload.all_recent_items || [], itemText);
  renderCards(els.highlightItems, payload.highlights || [], itemText);
  renderTopics(payload.topics || []);
  renderCards(els.threadItems, payload.open_threads || [], itemText);
  renderCards(els.summaryItems, payload.summaries || [], (item) => item.summary || item.body || "");
}

function renderViewers() {
  const source = state.memory?.viewers || state.overview?.viewers || {};
  const items = (source.items || []).filter((item) => {
    if (!state.viewerFilter) return true;
    return `${item.display_name || ""} ${item.live_username || ""}`.toLowerCase().includes(state.viewerFilter);
  });
  if (!items.length) {
    els.viewerRows.innerHTML = emptyText("暂时没有符合条件的观众画像。");
    return;
  }
  els.viewerRows.innerHTML = items.map((item) => {
    const counts = item.event_counts || {};
    const danmaku = (item.recent_danmaku || []).slice(0, 3).map((row) => row.content).filter(Boolean).join(" / ");
    return `
      <article class="viewer-card">
        <div>
          <h2>${escapeHtml(item.display_name || item.live_username || item.key)}</h2>
          <span>${escapeHtml(item.live_username || "已匹配关系节点")}</span>
        </div>
        <b>${escapeHtml(item.total_events || 0)}</b>
        <p>${escapeHtml(eventCountText(counts))}</p>
        <small>${escapeHtml(danmaku || "暂无最近弹幕样本")}</small>
      </article>
    `;
  }).join("");
}

function renderEvents() {
  const events = state.overview?.recent_events || [];
  els.eventCount.textContent = `${events.length} 条`;
  if (!events.length) {
    els.eventRows.innerHTML = emptyText("暂时没有直播事件。");
    return;
  }
  els.eventRows.innerHTML = events.map((item) => `
    <article class="event-row">
      <span>${escapeHtml(`${platformText(item.platform)} · ${liveEventTypeText(item)}`)}</span>
      <div>
        <b>${escapeHtml(item.username || "系统")}</b>
        <p>${escapeHtml(item.content || item.display || "--")}</p>
      </div>
      <time>${escapeHtml(formatTime(item.ts))}</time>
    </article>
  `).join("");
}

function platformText(platform) {
  return String(platform || "").toLowerCase() === "twitch" ? "Twitch" : "B站";
}

function liveEventTypeText(item) {
  if (String(item?.type || "") !== "danmaku") return String(item?.type || "未知事件");
  if (Number(item?.dm_type) === 1) return "表情弹幕";
  if (Number(item?.dm_type) === 2) return "语音弹幕";
  return "文字弹幕";
}

function renderConfig() {
  if (!els.configEditor) return;
  if (els.configStatus) {
    els.configStatus.textContent = state.configFallback
      ? "正在使用页面内置配置结构；若保存失败，请重载/重启插件让后端新接口生效。"
      : "已连接拓展页配置接口，保存后会写入插件配置。";
  }
  if (!Object.keys(state.configSchema).length) {
    els.configEditor.innerHTML = emptyText("配置结构加载中。");
    return;
  }
  const values = state.configDirty
    ? { ...state.configValues, ...collectConfigValues(false) }
    : { ...state.configValues };
  LiveConfigForm.renderGroups(els.configEditor, state.configGroups, state.configSchema, values, {
    includeGroup: (group) => group.id !== "subtitle",
    dynamic: { ...state.dynamicOptions, externalTts: ttsToolSource() },
  });
  updateExternalTtsFields();
  setDynamicNote("live_tts_external_tool_name", ttsNoteText());
  setDynamicNote(
    "live_tts_external_service_method",
    state.dynamicOptions.ttsMethods?.length ? `可用方法：${state.dynamicOptions.ttsMethods.join(" / ")}` : ""
  );

  els.configEditor.querySelectorAll(".config-control").forEach((control) => {
    control.addEventListener("input", () => {
      state.configDirty = true;
      updateDirtyState();
    });
    control.addEventListener("change", () => {
      state.configDirty = true;
      if (control.name === "live_tts_backend") updateExternalTtsFields();
      updateDirtyState();
    });
  });

  els.configEditor.querySelectorAll('select[data-dynamic-select="1"]').forEach((select) => {
    select.addEventListener("change", () => handleDynamicSelectChange(select));
  });
  els.configEditor.querySelectorAll('[data-action="scan-vts"]').forEach((button) => {
    button.addEventListener("click", scanVtsCandidates);
  });
  els.configEditor.querySelectorAll('[data-action="refresh-tts"]').forEach((button) => {
    button.addEventListener("click", refreshExternalTtsOptions);
  });
}

async function loadDynamicOptions(options = {}) {
  let loaded = false;
  try {
    const [tts, vts] = await Promise.all([
      LivePageApi.get("/options/external-tts").catch(() => null),
      LivePageApi.get("/options/vts-candidates").catch(() => null),
    ]);
    if (tts) {
      state.dynamicOptions.externalTts = Array.isArray(tts.services) ? tts.services : [];
      state.dynamicOptions.externalTtsAll = Array.isArray(tts.tools) ? tts.tools : [];
      state.dynamicOptions.ttsStats = {
        total: Number(tts.totalTools || 0),
        resolved: Number(tts.resolvedTools || 0),
        services: state.dynamicOptions.externalTts.length,
      };
      loaded = true;
    }
    if (vts) {
      state.dynamicOptions.vtsCandidates = Array.isArray(vts.candidates) ? vts.candidates : [];
      loaded = true;
    }
    syncTtsMethodChoices();
    if (loaded && Object.keys(state.configSchema).length) renderConfig();
    return loaded;
  } catch (error) {
    if (!options.silent) showToast(error.message || String(error));
    return false;
  }
}

function currentFieldValue(key) {
  const control = els.configEditor?.querySelector(`[name="${key}"]`);
  if (control && typeof control.value === "string") return control.value;
  return String(state.configValues?.[key] ?? "");
}

function ttsToolSource() {
  const services = state.dynamicOptions.externalTts || [];
  if (services.length) return services;
  return state.dynamicOptions.externalTtsAll || [];
}

function syncTtsMethodChoices() {
  const tool = currentFieldValue("live_tts_external_tool_name") || state.configValues?.live_tts_external_tool_name || "";
  const service = ttsToolSource().find((item) => item.tool === tool);
  state.dynamicOptions.ttsMethods = service?.methods?.length ? service.methods : [];
  state.dynamicOptions.selectedTool = tool;
}

function ttsNoteText() {
  const stats = state.dynamicOptions.ttsStats;
  if (!stats) return "";
  if (!stats.total) {
    return "没有读取到已注册的 LLM 工具：先在插件里用 @llm_tool / filter.llm_tool 注册工具，再点「刷新列表」。";
  }
  if (!stats.services) {
    return `已注册 ${stats.total} 个工具，但没有识别到带合成方法的服务；下拉里列出全部工具，方法名需要手动填写（也可参考插件文档）。`;
  }
  return `已注册 ${stats.total} 个工具，识别到 ${stats.services} 个可合成服务；选中后会自动列出可用方法。`;
}

function deriveScanSubnet() {
  const host = String(window.location.hostname || "");
  const match = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!match) return "";
  const octets = match.slice(1, 5).map((part) => Number(part));
  if (octets.some((value) => !Number.isInteger(value) || value < 0 || value > 255)) return "";
  const [a, b, c] = octets;
  const isPrivate = a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
  return isPrivate ? `${a}.${b}.${c}.0/24` : "";
}

function applySelectedTtsTool(tool) {
  const service = (state.dynamicOptions.externalTts || []).find((item) => item.tool === tool);
  const pluginInput = els.configEditor?.querySelector('[name="live_tts_external_plugin_name"]');
  if (pluginInput && service?.plugin) pluginInput.value = service.plugin;
  state.dynamicOptions.ttsMethods = service?.methods?.length ? service.methods : [];
  state.dynamicOptions.selectedTool = tool;
}

function applySelectedVtsHost(host) {
  const candidate = (state.dynamicOptions.vtsCandidates || []).find((item) => item.host === host);
  if (!candidate) return;
  const portInput = els.configEditor?.querySelector('[name="vts_port"]');
  if (portInput && candidate.port) portInput.value = String(candidate.port);
}

function setDynamicNote(key, text) {
  const note = els.configEditor?.querySelector(`[data-config-note="${key}"]`);
  if (note) note.textContent = text || "";
}

function handleDynamicSelectChange(select) {
  const key = select.name;
  if (select.value === "__custom__") {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "config-control";
    input.id = select.id;
    input.name = key;
    input.value = "";
    input.placeholder = "手动填写，例如 192.168.1.10 或 demo_tts_tool";
    select.replaceWith(input);
    input.focus();
    state.configDirty = true;
    updateDirtyState();
    return;
  }
  if (key === "live_tts_external_tool_name") {
    applySelectedTtsTool(select.value);
    const service = (state.dynamicOptions.externalTts || []).find((item) => item.tool === select.value);
    renderConfig();
    setDynamicNote("live_tts_external_tool_name", service ? `可用方法：${(service.methods || []).join(" / ")}` : "");
  } else if (key === "vts_host") {
    applySelectedVtsHost(select.value);
  }
  state.configDirty = true;
  updateDirtyState();
}

async function scanVtsCandidates() {
  state.dynamicOptions.vtsScanning = true;
  renderConfig();
  try {
    const subnet = deriveScanSubnet();
    const query = subnet ? `?mode=scan&subnet=${encodeURIComponent(subnet)}` : "?mode=scan";
    const data = await LivePageApi.get(`/options/vts-candidates${query}`);
    state.dynamicOptions.vtsCandidates = Array.isArray(data.candidates) ? data.candidates : [];
    const count = state.dynamicOptions.vtsCandidates.length;
    const scanned = data.scanned || {};
    showToast(count
      ? `发现 ${count} 个 VTS（已扫描 ${scanned.hosts || 0} 个地址）。`
      : `未发现 VTS，已扫描 ${scanned.hosts || 0} 个地址；可在网段输入框里手动指定。`);
  } catch (error) {
    showToast(error.message || String(error));
  } finally {
    state.dynamicOptions.vtsScanning = false;
    renderConfig();
  }
}

async function refreshExternalTtsOptions() {
  state.dynamicOptions.ttsRefreshing = true;
  renderConfig();
  try {
    const data = await LivePageApi.get("/options/external-tts");
    state.dynamicOptions.externalTts = Array.isArray(data.services) ? data.services : [];
    state.dynamicOptions.externalTtsAll = Array.isArray(data.tools) ? data.tools : [];
    state.dynamicOptions.ttsStats = {
      total: Number(data.totalTools || 0),
      resolved: Number(data.resolvedTools || 0),
      services: state.dynamicOptions.externalTts.length,
    };
    syncTtsMethodChoices();
    showToast(state.dynamicOptions.externalTts.length
      ? `已加载 ${state.dynamicOptions.externalTts.length} 个外部 TTS 服务。`
      : "没有检测到带公开合成方法的外部 TTS 服务。");
  } catch (error) {
    showToast(error.message || String(error));
  } finally {
    state.dynamicOptions.ttsRefreshing = false;
    renderConfig();
  }
}

function updateExternalTtsFields() {
  const backend = els.configEditor?.querySelector('[name="live_tts_backend"]')?.value;
  const showExternal = backend === "registered_service" || backend === "auto";
  [
    "live_tts_external_tool_name",
    "live_tts_external_service_method",
    "live_tts_external_plugin_name",
    "live_tts_external_timeout_seconds",
  ].forEach((key) => {
    const field = els.configEditor?.querySelector(`[data-config-key="${key}"]`);
    if (field) field.hidden = !showExternal;
  });
}

function collectConfigValues(includeFallback = true) {
  return LiveConfigForm.collectValues(
    els.configEditor,
    state.configSchema,
    includeFallback ? state.configValues : {},
  );
}

function updateDirtyState() {
  if (els.configDirtyBadge) els.configDirtyBadge.hidden = !state.configDirty;
  if (els.saveConfigBtn) els.saveConfigBtn.disabled = !state.configDirty;
}

function renderMetricList(target, items) {
  target.innerHTML = items.map(([label, value]) => `
    <div class="metric-row">
      <span>${escapeHtml(label)}</span>
      <b>${escapeHtml(value)}</b>
    </div>
  `).join("");
}

function renderCards(target, items, getText) {
  if (!items.length) {
    target.innerHTML = emptyText("暂无数据。");
    return;
  }
  target.innerHTML = items.map((item) => `
    <div class="mini-card">
      <span>${escapeHtml(item.type || item.username || item.date || "直播")}</span>
      <p>${escapeHtml(getText(item) || "--")}</p>
    </div>
  `).join("");
}

function renderTopics(items) {
  if (!items.length) {
    els.topicItems.innerHTML = emptyText("暂无话题。");
    return;
  }
  els.topicItems.innerHTML = items.map((item) => `
    <span class="topic">
      <b>${escapeHtml(item.topic)}</b>
      <small>${escapeHtml(item.count)} 次</small>
    </span>
  `).join("");
}

function itemText(item) {
  return item.text || item.content || item.summary || item.body || "";
}

function eventCountText(counts) {
  const labels = {
    danmaku: "弹幕",
    gift: "礼物",
    super_chat: "SC",
    buy_guard: "上舰",
    enter_room: "进房",
    follow: "关注",
    like: "点赞",
  };
  return Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .map(([key, value]) => `${labels[key] || key} ${value}`)
    .join("、") || "暂无分类";
}

async function loadSoullink(options = {}) {
  try {
    state.soullink = await LivePageApi.get("/soullink/status");
    renderSoullink();
    loadGazeStatus();
    return state.soullink;
  } catch (error) {
    if (!options.silent) showToast(error.message || String(error));
    if (els.soullinkSummary) els.soullinkSummary.textContent = "Soullink 状态接口暂不可用。";
    return null;
  }
}

async function loadGazeStatus() {
  if (state.gazeStatusLoading) return;
  state.gazeStatusLoading = true;
  try {
    const st = await LivePageApi.get("/soullink/gaze/status");
    if (els.gazeToggle) {
      els.gazeToggle.checked = !!st.enabled;
    }
    if (els.gazeStatus) {
      if (!st.enabled) {
        els.gazeStatus.textContent = "未启用";
        els.gazeStatus.className = "gaze-status off";
      } else if (!st.soullink_enabled || !st.running) {
        els.gazeStatus.textContent = "已启用但 Soullink 未运行";
        els.gazeStatus.className = "gaze-status on";
      } else if (st.tracking) {
        els.gazeStatus.textContent = "运行中";
        els.gazeStatus.className = "gaze-status on";
      } else {
        els.gazeStatus.textContent = "等待 VTS 鼠标数据";
        els.gazeStatus.className = "gaze-status on";
      }
    }
    // 鼠标位置点
    if (els.gazeStage && typeof st.x === "number") {
      const pctX = (Math.max(0, Math.min(1, st.x)) * 100).toFixed(1);
      const pctY = (Math.max(0, Math.min(1, st.y)) * 100).toFixed(1);
      els.gazeDot.style.left = pctX + "%";
      els.gazeDot.style.top = pctY + "%";
      if (els.gazeCoords) {
        els.gazeCoords.textContent = `${st.x.toFixed(2)} ${st.y.toFixed(2)}`;
      }
    }
  } catch (error) {
    if (els.gazeStatus) els.gazeStatus.textContent = "接口不可用";
  } finally {
    state.gazeStatusLoading = false;
  }
}

async function toggleGaze() {
  const enabled = !!els.gazeToggle?.checked;
  try {
    await LivePageApi.post("/config/save", { values: { soullink_gaze_enabled: enabled } });
    showToast(enabled ? "鼠标视线追踪已开启。" : "鼠标视线追踪已关闭，停止轮询 VTS 鼠标参数。");
  } catch (error) {
    showToast(error.message || String(error));
  }
  await loadGazeStatus();
}

async function controlSoullink(action, extra = {}) {
  try {
    const data = await LivePageApi.post("/soullink/control", { action, ...extra });
    if (data.status) state.soullink = data.status;
    renderSoullink();
    showToast(data.message || "Soullink 操作已完成。");
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function triggerSoullink() {
  await controlSoullink("test", {
    emotion: state.soullinkEmotion,
    intensity: Number(els.soullinkIntensity?.value || 0.8),
    vad: {
      valence: Number(els.soullinkValence?.value || 0),
      arousal: Number(els.soullinkArousal?.value || 0),
      dominance: Number(els.soullinkDominance?.value || 0),
    },
  });
}

function handleSoullinkPreset(event) {
  const button = event.target.closest("button[data-emotion]");
  if (!button) return;
  state.soullinkEmotion = button.dataset.emotion || "neutral";
  if (els.soullinkValence) els.soullinkValence.value = button.dataset.v || "0";
  if (els.soullinkArousal) els.soullinkArousal.value = button.dataset.a || "0";
  if (els.soullinkDominance) els.soullinkDominance.value = button.dataset.d || "0";
  els.soullinkPresets?.querySelectorAll("button").forEach((item) => {
    item.classList.toggle("is-selected", item === button);
  });
  updateSoullinkControlValues();
}

function updateSoullinkControlValues() {
  const bindings = [
    [els.soullinkIntensity, els.soullinkIntensityValue],
    [els.soullinkValence, els.soullinkValenceValue],
    [els.soullinkArousal, els.soullinkArousalValue],
    [els.soullinkDominance, els.soullinkDominanceValue],
  ];
  bindings.forEach(([control, output]) => {
    if (control && output) output.value = Number(control.value || 0).toFixed(2);
  });
  const selected = els.soullinkPresets?.querySelector("button.is-selected");
  if (!selected) {
    els.soullinkPresets?.querySelector(`button[data-emotion="${state.soullinkEmotion}"]`)?.classList.add("is-selected");
  }
}

function renderSoullink() {
  const data = state.soullink || {};
  const snapshot = data.snapshot || {};
  const intent = snapshot.intent || {};
  const vad = snapshot.vad || {};
  const currentVad = vad.current || {};
  const facs = snapshot.live2dParams || snapshot.facs || {};
  const scheduler = data.scheduler || {};
  const running = Boolean(data.running);

  if (els.soullinkBadge) {
    els.soullinkBadge.textContent = running ? "运行中" : (data.enabled ? "已启用" : "未启用");
    els.soullinkBadge.className = `badge ${running ? "ok" : "idle"}`;
  }
  if (els.soullinkSummary) {
    els.soullinkSummary.textContent = running
      ? `Emotion Engine ${data.version || ""} · ${data.mode || "emotion"} 模式 · ${data.fps || 0} FPS`
      : (data.last_error || (data.enabled ? "引擎已启用但尚未运行。" : "默认关闭；请在配置页开启后保存。"));
  }
  if (els.soullinkState) els.soullinkState.textContent = snapshot.state || "IDLE";
  if (els.soullinkEmotion) {
    els.soullinkEmotion.textContent = snapshot.state === "IDLE"
      ? (vad.dominantEmotion || "neutral")
      : (intent.emotion || vad.dominantEmotion || "neutral");
  }
  if (els.soullinkVariant) {
    els.soullinkVariant.textContent = intent.variant || (running ? "持续情绪与 Idle 动作运行中" : "等待引擎启动");
  }
  if (els.soullinkStyle && document.activeElement !== els.soullinkStyle) {
    els.soullinkStyle.value = data.style || "natural";
  }
  if (els.soullinkStartBtn) els.soullinkStartBtn.disabled = running || !data.enabled;
  if (els.soullinkStopBtn) els.soullinkStopBtn.disabled = !running;
  if (els.soullinkResetBtn) els.soullinkResetBtn.disabled = !running;
  if (els.soullinkTriggerBtn) els.soullinkTriggerBtn.disabled = !running;
  const vtsConnected = Boolean(data.vts?.connected ?? scheduler.vts_connected);
  if (els.soullinkParamsBtn) {
    els.soullinkParamsBtn.disabled = !vtsConnected;
    els.soullinkParamsBtn.title = vtsConnected
      ? "读取当前 VTube Studio 模型参数"
      : "VTube Studio 未连接，暂时无法读取模型参数";
  }
  if (els.soullinkMappingBtn) {
    els.soullinkMappingBtn.title = vtsConnected
      ? "打开当前模型的高级参数校准"
      : "可离线编辑映射；连接 VTube Studio 后会显示模型范围";
  }
  if (els.soullinkVtsNotice) {
    els.soullinkVtsNotice.className = `soullink-vts-notice ${vtsConnected ? "is-ok" : "is-warning"}`;
    els.soullinkVtsNotice.textContent = vtsConnected
      ? "VTS 已连接：测试台参数会实时发送到当前模型。"
      : "VTS 未连接：当前显示的是本地情绪与 FACS 预览；启动 VTube Studio 并完成认证后才会发送真实模型参数。";
  }

  const headX = Number(facs.headX || 0);
  const headY = Number(facs.headY || 0);
  const headZ = Number(facs.headZ || 0);
  const smile = Number(facs.mouthSmile || 0);
  const eyeOpen = Number(facs.eyeOpen ?? 1);
  if (els.soullinkCharacterVisual && !window.Live2DPreview?.hasModel()) {
    els.soullinkCharacterVisual.style.transform = `translate(${headX * 42}px, ${headY * -24}px) rotate(${headZ * 24}deg)`;
    els.soullinkCharacterVisual.style.setProperty("--emotion-saturation", String(0.86 + Math.max(0, smile) * 0.42));
    els.soullinkCharacterVisual.style.setProperty("--eye-open", String(Math.max(0.65, eyeOpen)));
  }
  window.Live2DPreview?.setFacs(facs);

  renderSoullinkRuntimeMetrics(data, scheduler);
  renderSoullinkVad(currentVad, vad.target || {});
  renderSoullinkFacs(facs);
  renderSoullinkParameters(data.vts_parameters || []);
  updateSoullinkMappingLiveValues(snapshot, data.vts_parameters || []);
}

async function importLive2DModel(event) {
  const input = event.currentTarget;
  const files = input?.files;
  if (!files?.length) return;
  try {
    if (els.live2dImportBtn) els.live2dImportBtn.disabled = true;
    const modelName = await window.Live2DPreview.loadFiles(files);
    showToast(`${modelName} 已载入页面预览。`);
  } catch (error) {
    showToast(error?.message || String(error));
  } finally {
    if (els.live2dImportBtn) els.live2dImportBtn.disabled = false;
    input.value = "";
  }
}

function renderLive2DModelStatus(detail = {}) {
  if (els.live2dModelStatus) {
    els.live2dModelStatus.textContent = detail.message || "";
    els.live2dModelStatus.className = `live2d-model-status is-${detail.status || "idle"}`;
  }
  if (els.live2dRemoveBtn) els.live2dRemoveBtn.hidden = !detail.hasModel;
  if (els.live2dImportBtn) {
    els.live2dImportBtn.textContent = detail.hasModel ? "更换 L2D" : "导入 L2D";
  }
  renderLive2DZoom(detail);
}

function renderLive2DZoom(detail = {}) {
  const hasModel = Boolean(detail.hasModel ?? window.Live2DPreview?.hasModel());
  const zoom = Number(detail.zoom ?? window.Live2DPreview?.getZoom?.() ?? 1);
  const minZoom = Number(detail.minZoom ?? 0.25);
  const maxZoom = Number(detail.maxZoom ?? 4);
  if (els.live2dZoomControls) els.live2dZoomControls.hidden = !hasModel;
  if (els.live2dZoomSlider && document.activeElement !== els.live2dZoomSlider) {
    els.live2dZoomSlider.value = String(Math.round(zoom * 100));
  }
  if (els.live2dZoomValue) els.live2dZoomValue.value = `${Math.round(zoom * 100)}%`;
  if (els.live2dZoomOutBtn) els.live2dZoomOutBtn.disabled = !hasModel || zoom <= minZoom + 0.001;
  if (els.live2dZoomInBtn) els.live2dZoomInBtn.disabled = !hasModel || zoom >= maxZoom - 0.001;
  if (els.live2dZoomResetBtn) els.live2dZoomResetBtn.disabled = !hasModel || Math.abs(zoom - 1) < 0.001;
}

function renderSoullinkRuntimeMetrics(data, scheduler) {
  if (!els.soullinkRuntimeMetrics) return;
  const items = [
    ["模式", data.mode || "emotion"],
    ["引擎帧", data.frames_received || 0],
    ["VTS 帧", scheduler.frames_sent || 0],
    ["VTS 状态", (data.vts?.connected ?? scheduler.vts_connected) ? "已连接" : "未连接"],
    ["混合层", (scheduler.layers || []).join(" + ") || "待命"],
  ];
  els.soullinkRuntimeMetrics.innerHTML = items.map(([label, value]) => `
    <div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>
  `).join("");
}

function renderSoullinkVad(current, target) {
  if (!els.soullinkVadMeters) return;
  const items = [
    ["Valence", Number(current.valence || 0), Number(target.valence || 0), "positive"],
    ["Arousal", Number(current.arousal || 0), Number(target.arousal || 0), "energy"],
    ["Dominance", Number(current.dominance || 0), Number(target.dominance || 0), "control"],
  ];
  els.soullinkVadMeters.innerHTML = items.map(([label, value, goal, tone]) => `
    <div class="vad-meter ${tone}">
      <div><span>${escapeHtml(label)}</span><b>${value.toFixed(3)}</b></div>
      <div class="bipolar-track">
        <span class="bipolar-fill" style="left:${value < 0 ? 50 - Math.abs(value) * 50 : 50}%;width:${Math.abs(value) * 50}%"></span>
        <i style="left:${((goal + 1) / 2) * 100}%" title="目标 ${goal.toFixed(3)}"></i>
      </div>
    </div>
  `).join("");
}

function renderSoullinkFacs(facs) {
  if (!els.soullinkFacsMeters) return;
  const keys = [
    "mouthSmile", "eyeSmile", "eyeOpen", "browInnerUp", "browDown", "mouthFrown",
    "gazeX", "gazeY", "headX", "headY", "headZ", "breath", "blush", "tear",
  ];
  els.soullinkFacsMeters.innerHTML = keys.map((key) => {
    const value = Number(facs[key] || 0);
    return `
      <div class="facs-row">
        <span>${escapeHtml(key)}</span>
        <div><i style="width:${Math.min(100, Math.abs(value) * 100)}%"></i></div>
        <b>${value.toFixed(3)}</b>
      </div>
    `;
  }).join("");
}

function renderSoullinkParameters(parameters) {
  if (!els.soullinkParameterRows) return;
  if (!parameters.length) {
    els.soullinkParameterRows.innerHTML = emptyText("引擎运行后，这里会显示发送给 VTS 的追踪参数。");
    return;
  }
  els.soullinkParameterRows.innerHTML = parameters.map((item) => `
    <div class="parameter-row">
      <span>${escapeHtml(item.id)}</span>
      <div><i style="width:${Math.min(100, Math.abs(Number(item.value || 0)) / 30 * 100)}%"></i></div>
      <b>${Number(item.value || 0).toFixed(3)}</b>
    </div>
  `).join("");
}

async function loadSoullinkParameters() {
  try {
    els.soullinkParamsBtn.disabled = true;
    state.soullinkParameters = await LivePageApi.get("/soullink/vts-parameters");
    renderSoullinkParameterCatalog();
    showToast("已读取 VTS 追踪输入与 Live2D 模型参数。");
  } catch (error) {
    showToast(error.message || String(error));
  } finally {
    els.soullinkParamsBtn.disabled = false;
  }
}

function renderSoullinkParameterCatalog() {
  if (!els.soullinkModelParameters) return;
  const data = state.soullinkParameters || {};
  const sections = [
    ["VTS 追踪输入", data.inputs || []],
    ["Live2D 输出参数", data.live2d || []],
  ];
  els.soullinkModelParameters.innerHTML = sections.map(([title, items]) => `
    <section>
      <h3>${escapeHtml(title)} <span>${items.length}</span></h3>
      <div>${items.slice(0, 120).map((item) => `
        <span class="parameter-chip" title="${escapeHtml(`${item.min ?? "?"} ~ ${item.max ?? "?"}`)}">
          ${escapeHtml(item.name || item.id || "?")}
        </span>
      `).join("") || emptyText("暂无参数")}</div>
    </section>
  `).join("");
}

async function openSoullinkMapping() {
  if (!els.soullinkMappingWorkbench) return;
  els.soullinkMappingWorkbench.hidden = false;
  if (state.soullinkMappingDraft && state.soullinkMappingDirty) {
    renderSoullinkMappingWorkbench();
    return;
  }
  if (els.soullinkMappingBtn) els.soullinkMappingBtn.disabled = true;
  if (els.soullinkMappingStatus) els.soullinkMappingStatus.textContent = "正在读取当前模型与映射...";
  try {
    const data = await LivePageApi.get("/soullink/mapping");
    state.soullinkMapping = data;
    state.soullinkMappingDraft = cloneJson(data.activeMapping || data.savedMapping || data.defaultMapping);
    state.soullinkMappingDirty = Boolean(data.previewActive);
    state.soullinkMappingPreviewing = Boolean(data.previewActive);
    state.soullinkParameters = {
      inputs: data.inputs || [],
      live2d: data.live2d || [],
      mapped: state.soullink?.vts_parameters || [],
    };
    renderSoullinkMappingWorkbench();
    renderSoullinkParameterCatalog();
  } catch (error) {
    if (els.soullinkMappingStatus) els.soullinkMappingStatus.textContent = error.message || String(error);
    showToast(error.message || String(error));
  } finally {
    if (els.soullinkMappingBtn) els.soullinkMappingBtn.disabled = false;
  }
}

async function closeSoullinkMapping() {
  if (!els.soullinkMappingWorkbench || els.soullinkMappingWorkbench.hidden) return;
  if (state.soullinkMappingDirty && !window.confirm("关闭并撤销未保存的高级映射预览？")) return;
  if (state.soullinkMappingPreviewing) {
    await discardSoullinkMappingPreview({ silent: true });
  }
  els.soullinkMappingWorkbench.hidden = true;
  state.soullinkMappingDraft = null;
  state.soullinkMappingDirty = false;
}

function renderSoullinkMappingWorkbench() {
  const data = state.soullinkMapping || {};
  const draft = state.soullinkMappingDraft;
  if (!draft) return;
  renderSoullinkVtsInputOptions();
  renderSoullinkCompositeFields();
  renderSoullinkMappingRules();
  syncSoullinkMappingJson();
  renderSoullinkMappingChrome();
  if (els.soullinkMappingModel) {
    const model = data.model || {};
    els.soullinkMappingModel.textContent = model.loaded
      ? `${model.name || "当前模型"}${model.id ? ` · ${model.id.slice(0, 8)}` : ""}`
      : (data.connected ? "未加载模型" : "VTS 离线");
  }
}

function renderSoullinkVtsInputOptions() {
  if (!els.soullinkVtsInputOptions) return;
  const inputs = [...(state.soullinkMapping?.inputs || [])].sort((left, right) => {
    const usedDelta = Number(Boolean(right.usedByModel)) - Number(Boolean(left.usedByModel));
    return usedDelta || String(left.name || "").localeCompare(String(right.name || ""));
  });
  els.soullinkVtsInputOptions.innerHTML = inputs.map((item) => {
    const label = item.usedByModel
      ? `当前模型已绑定 · ${item.min ?? "?"} ~ ${item.max ?? "?"}`
      : `${item.kind || "input"} · ${item.min ?? "?"} ~ ${item.max ?? "?"}`;
    return `<option value="${escapeHtml(item.name || "")}" label="${escapeHtml(label)}"></option>`;
  }).join("");
}

function renderSoullinkCompositeFields() {
  if (!els.soullinkCompositeFields) return;
  const composites = state.soullinkMappingDraft?.composites || {};
  const defaults = state.soullinkMapping?.compositeDefaults || {};
  els.soullinkCompositeFields.innerHTML = Object.keys(defaults).map((key) => `
    <label for="mapping-composite-${escapeHtml(key)}">
      <span>${escapeHtml(SOULLINK_COMPOSITE_LABELS[key] || key)}</span>
      <input id="mapping-composite-${escapeHtml(key)}" type="number" step="0.01"
        data-composite-field="${escapeHtml(key)}" value="${escapeHtml(mappingNumber(composites[key], defaults[key]))}">
    </label>
  `).join("");
}

function renderSoullinkMappingRules() {
  if (!els.soullinkMappingRules) return;
  const rules = state.soullinkMappingDraft?.rules || [];
  const validation = validateSoullinkMappingDraft();
  const issuesByRule = new Map();
  validation.issues.forEach((issue) => {
    if (!issuesByRule.has(issue.ruleId)) issuesByRule.set(issue.ruleId, []);
    issuesByRule.get(issue.ruleId).push(issue);
  });
  if (!rules.length) {
    els.soullinkMappingRules.innerHTML = emptyText("当前自定义映射没有规则。");
    return;
  }
  els.soullinkMappingRules.innerHTML = rules.map((rule) => {
    const issues = issuesByRule.get(rule.id) || [];
    const severity = issues.some((item) => item.level === "error")
      ? "has-error"
      : (issues.length ? "has-warning" : "");
    const inputMeta = getSoullinkMappingInput(rule.target);
    const targetKind = soullinkMappingTargetKind(rule.target, inputMeta);
    return `
      <article class="mapping-rule ${rule.enabled ? "" : "is-disabled"} ${severity}" data-mapping-rule="${escapeHtml(rule.id)}">
        <div class="mapping-rule-main">
          <label class="mapping-enable-field" title="启用规则">
            <input type="checkbox" data-rule-id="${escapeHtml(rule.id)}" data-field="enabled" ${rule.enabled ? "checked" : ""} aria-label="启用 ${escapeHtml(rule.source)} 到 ${escapeHtml(rule.target)} 的映射">
          </label>
          <select data-rule-id="${escapeHtml(rule.id)}" data-field="source" aria-label="Soullink 源通道">
            ${soullinkSourceOptions(rule.source)}
          </select>
          <span class="mapping-direction" aria-hidden="true">→</span>
          <div class="mapping-target-wrap">
            <input type="text" list="soullinkVtsInputOptions" data-rule-id="${escapeHtml(rule.id)}" data-field="target"
              value="${escapeHtml(rule.target)}" aria-label="VTS 追踪输入">
            <span class="mapping-target-kind">${escapeHtml(targetKind)}</span>
          </div>
          <div class="mapping-live-value" aria-label="实时源值与输出值">
            <output id="mapping-source-live-${escapeHtml(rule.id)}">--</output>
            <span>→</span>
            <output id="mapping-target-live-${escapeHtml(rule.id)}">--</output>
          </div>
          <button class="mapping-delete-button" type="button" data-mapping-action="delete" data-rule-id="${escapeHtml(rule.id)}" title="删除规则" aria-label="删除规则">×</button>
        </div>
        <details>
          <summary>锚点、曲线与混合</summary>
          <div class="mapping-rule-details">
            ${mappingAnchorGroup(rule, "source", "源通道锚点", ["sourceMin", "sourceNeutral", "sourceMax"])}
            ${mappingAnchorGroup(rule, "output", "VTS 输出锚点", ["outputMin", "outputNeutral", "outputMax"])}
            <div class="mapping-option-grid">
              ${mappingNumberField(rule, "curve", "响应曲线", 0.05)}
              ${mappingNumberField(rule, "deadzone", "中心死区", 0.01)}
              ${mappingNumberField(rule, "smoothing", "额外平滑（秒）", 0.01)}
              ${mappingNumberField(rule, "weight", "VTS 权重", 0.01)}
              <label><span>同目标混合</span><select data-rule-id="${escapeHtml(rule.id)}" data-field="blend">
                ${["replace", "add", "max", "min"].map((mode) => `<option value="${mode}" ${rule.blend === mode ? "selected" : ""}>${mode}</option>`).join("")}
              </select></label>
              <label class="mapping-check-field"><input type="checkbox" data-rule-id="${escapeHtml(rule.id)}" data-field="invert" ${rule.invert ? "checked" : ""}><span>反转方向</span></label>
              <label class="mapping-check-field"><input type="checkbox" data-rule-id="${escapeHtml(rule.id)}" data-field="clamp" ${rule.clamp ? "checked" : ""}><span>限制锚点范围</span></label>
              <button class="mapping-use-range-button" type="button" data-mapping-action="use-range" data-rule-id="${escapeHtml(rule.id)}" ${inputMeta ? "" : "disabled"}>采用模型范围</button>
            </div>
          </div>
        </details>
        ${issues.length ? `<p class="mapping-rule-issue ${issues.some((item) => item.level === "error") ? "is-error" : ""}">${escapeHtml(issues.map((item) => item.message).join("；"))}</p>` : ""}
      </article>
    `;
  }).join("");
}

function mappingAnchorGroup(rule, prefix, legend, fields) {
  const labels = prefix === "source" ? ["低位", "中性", "高位"] : ["低位", "中性", "高位"];
  return `
    <fieldset class="mapping-anchor-group">
      <legend>${escapeHtml(legend)}</legend>
      <div class="mapping-anchor-grid">
        ${fields.map((field, index) => `
          <label><span>${labels[index]}</span><input type="number" step="0.01" data-rule-id="${escapeHtml(rule.id)}" data-field="${field}" value="${escapeHtml(mappingNumber(rule[field], 0))}"></label>
        `).join("")}
      </div>
    </fieldset>
  `;
}

function mappingNumberField(rule, field, label, step) {
  return `<label><span>${escapeHtml(label)}</span><input type="number" step="${step}" data-rule-id="${escapeHtml(rule.id)}" data-field="${field}" value="${escapeHtml(mappingNumber(rule[field], 0))}"></label>`;
}

function soullinkSourceOptions(current) {
  const groups = new Map();
  (state.soullinkMapping?.sources || []).forEach((source) => {
    const group = source.group || "其他";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(source);
  });
  if (current && !(state.soullinkMapping?.sources || []).some((item) => item.id === current)) {
    groups.set("自定义", [{ id: current, label: current }]);
  }
  return [...groups.entries()].map(([group, items]) => `
    <optgroup label="${escapeHtml(group)}">
      ${items.map((source) => `<option value="${escapeHtml(source.id)}" ${source.id === current ? "selected" : ""}>${escapeHtml(source.label || source.id)} · ${escapeHtml(source.id)}</option>`).join("")}
    </optgroup>
  `).join("");
}

function getSoullinkMappingInput(name) {
  return (state.soullinkMapping?.inputs || []).find((item) => item.name === name) || null;
}

function soullinkMappingTargetKind(target, inputMeta) {
  if (inputMeta?.usedByModel) return "已绑定";
  if (inputMeta) return inputMeta.kind === "custom" ? "自定义" : "未绑定";
  if ((state.soullinkMapping?.live2d || []).some((item) => item.name === target)) return "输出 ID";
  return target ? "未识别" : "未选择";
}

function handleSoullinkMappingInput(event) {
  const control = event.target.closest("[data-rule-id][data-field]");
  if (!control || !state.soullinkMappingDraft) return;
  const rule = state.soullinkMappingDraft.rules.find((item) => item.id === control.dataset.ruleId);
  if (!rule) return;
  const field = control.dataset.field;
  if (control.type === "checkbox") {
    rule[field] = control.checked;
  } else if (control.type === "number") {
    const value = Number(control.value);
    if (!Number.isFinite(value)) return;
    rule[field] = value;
  } else {
    rule[field] = control.value.trim();
  }
  if (field === "source" && event.type === "change") {
    const meta = (state.soullinkMapping.sources || []).find((item) => item.id === rule.source);
    if (meta) {
      rule.sourceMin = Number(meta.min);
      rule.sourceNeutral = Number(meta.neutral);
      rule.sourceMax = Number(meta.max);
    }
  }
  markSoullinkMappingDirty();
  if (event.type === "change" && ["enabled", "source", "target", "blend", "invert", "clamp"].includes(field)) {
    renderSoullinkMappingRules();
  }
}

function handleSoullinkCompositeInput(event) {
  const control = event.target.closest("[data-composite-field]");
  if (!control || !state.soullinkMappingDraft) return;
  const value = Number(control.value);
  if (!Number.isFinite(value)) return;
  state.soullinkMappingDraft.composites[control.dataset.compositeField] = value;
  markSoullinkMappingDirty();
}

function handleSoullinkMappingClick(event) {
  const button = event.target.closest("button[data-mapping-action][data-rule-id]");
  if (!button || !state.soullinkMappingDraft) return;
  const ruleIndex = state.soullinkMappingDraft.rules.findIndex((item) => item.id === button.dataset.ruleId);
  if (ruleIndex < 0) return;
  const rule = state.soullinkMappingDraft.rules[ruleIndex];
  if (button.dataset.mappingAction === "delete") {
    state.soullinkMappingDraft.rules.splice(ruleIndex, 1);
  } else if (button.dataset.mappingAction === "use-range") {
    const input = getSoullinkMappingInput(rule.target);
    if (!input) return;
    rule.outputMin = Number(input.min ?? rule.outputMin);
    rule.outputNeutral = Number(input.value ?? input.defaultValue ?? rule.outputNeutral);
    rule.outputMax = Number(input.max ?? rule.outputMax);
  }
  markSoullinkMappingDirty({ render: true });
}

function addSoullinkMappingRule() {
  const draft = state.soullinkMappingDraft;
  if (!draft) return;
  const source = (state.soullinkMapping?.sources || []).find((item) => item.id === "mouthOpen")
    || (state.soullinkMapping?.sources || [])[0]
    || { id: "mouthOpen", min: 0, neutral: 0, max: 1 };
  const input = getSoullinkMappingInput("MouthOpen")
    || (state.soullinkMapping?.inputs || []).find((item) => item.usedByModel)
    || (state.soullinkMapping?.inputs || [])[0]
    || { name: "", min: 0, value: 0, max: 1 };
  draft.rules.push({
    id: `custom-${Date.now().toString(36)}`,
    enabled: true,
    source: source.id,
    target: input.name || "",
    sourceMin: Number(source.min ?? -1),
    sourceNeutral: Number(source.neutral ?? 0),
    sourceMax: Number(source.max ?? 1),
    outputMin: Number(input.min ?? 0),
    outputNeutral: Number(input.value ?? input.defaultValue ?? 0),
    outputMax: Number(input.max ?? 1),
    curve: 1,
    deadzone: 0,
    smoothing: 0,
    weight: 1,
    invert: false,
    clamp: true,
    blend: "replace",
  });
  markSoullinkMappingDirty({ render: true });
}

async function captureSoullinkMappingNeutral() {
  if (!state.soullinkMappingDraft) return;
  if (els.soullinkMappingCaptureBtn) els.soullinkMappingCaptureBtn.disabled = true;
  try {
    await controlSoullink("reset");
    await sleep(450);
    const data = await LivePageApi.get("/soullink/mapping");
    state.soullinkMapping = { ...state.soullinkMapping, ...data };
    let captured = 0;
    state.soullinkMappingDraft.rules.forEach((rule) => {
      const input = getSoullinkMappingInput(rule.target);
      const value = Number(input?.value);
      if (!Number.isFinite(value)) return;
      rule.outputNeutral = value;
      captured += 1;
    });
    markSoullinkMappingDirty({ render: true });
    showToast(`已捕获 ${captured} 个当前 VTS 输入中性点。`);
  } catch (error) {
    showToast(error.message || String(error));
  } finally {
    if (els.soullinkMappingCaptureBtn) els.soullinkMappingCaptureBtn.disabled = false;
  }
}

function markSoullinkMappingDirty(options = {}) {
  state.soullinkMappingDirty = true;
  syncSoullinkMappingJson();
  if (options.render) {
    renderSoullinkMappingWorkbench();
  } else {
    renderSoullinkMappingChrome();
  }
  window.clearTimeout(state.soullinkMappingPreviewTimer);
  state.soullinkMappingPreviewTimer = window.setTimeout(() => {
    previewSoullinkMapping({ silent: true });
  }, 320);
}

async function previewSoullinkMapping(options = {}) {
  if (!state.soullinkMappingDraft) return false;
  window.clearTimeout(state.soullinkMappingPreviewTimer);
  const localValidation = validateSoullinkMappingDraft();
  if (localValidation.errors) {
    renderSoullinkMappingChrome();
    return false;
  }
  const requestId = ++state.soullinkMappingRequest;
  try {
    const data = await LivePageApi.post("/soullink/mapping/apply", {
      action: "preview",
      mapping: state.soullinkMappingDraft,
    });
    if (requestId !== state.soullinkMappingRequest) return false;
    state.soullinkMapping = { ...state.soullinkMapping, ...data };
    state.soullinkMappingPreviewing = true;
    if (options.adopt) {
      state.soullinkMappingDraft = cloneJson(data.activeMapping);
      renderSoullinkMappingWorkbench();
    } else {
      renderSoullinkMappingChrome();
    }
    return true;
  } catch (error) {
    if (requestId === state.soullinkMappingRequest && els.soullinkMappingStatus) {
      els.soullinkMappingStatus.textContent = error.message || String(error);
    }
    if (!options.silent) showToast(error.message || String(error));
    return false;
  }
}

async function saveSoullinkMapping() {
  if (!state.soullinkMappingDraft) return;
  const validation = validateSoullinkMappingDraft();
  if (validation.errors) {
    renderSoullinkMappingChrome();
    showToast("请先修正高级映射中的错误。");
    return;
  }
  if (els.soullinkMappingSaveBtn) els.soullinkMappingSaveBtn.disabled = true;
  try {
    const data = await LivePageApi.post("/soullink/mapping/apply", {
      action: "save",
      mapping: state.soullinkMappingDraft,
    });
    state.soullinkMapping = data;
    state.soullinkMappingDraft = cloneJson(data.savedMapping);
    state.soullinkMappingDirty = false;
    state.soullinkMappingPreviewing = false;
    state.configValues.soullink_vts_mapping = JSON.stringify(data.savedMapping);
    renderSoullinkMappingWorkbench();
    showToast(data.message || "高级映射已保存。");
  } catch (error) {
    showToast(error.message || String(error));
  } finally {
    if (els.soullinkMappingSaveBtn) els.soullinkMappingSaveBtn.disabled = false;
  }
}

async function resetSoullinkMapping() {
  if (!window.confirm("恢复内置映射并清除当前自定义规则？")) return;
  try {
    const data = await LivePageApi.post("/soullink/mapping/apply", { action: "reset" });
    state.soullinkMapping = data;
    state.soullinkMappingDraft = cloneJson(data.savedMapping);
    state.soullinkMappingDirty = false;
    state.soullinkMappingPreviewing = false;
    state.configValues.soullink_vts_mapping = "{}";
    renderSoullinkMappingWorkbench();
    showToast(data.message || "已恢复内置映射。");
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function discardSoullinkMappingPreview(options = {}) {
  try {
    const data = await LivePageApi.post("/soullink/mapping/apply", { action: "discard" });
    state.soullinkMapping = data;
    state.soullinkMappingDraft = cloneJson(data.savedMapping);
    state.soullinkMappingDirty = false;
    state.soullinkMappingPreviewing = false;
    renderSoullinkMappingWorkbench();
    if (!options.silent) showToast(data.message || "已撤销映射预览。");
  } catch (error) {
    if (!options.silent) showToast(error.message || String(error));
  }
}

async function importSoullinkMappingJson() {
  if (!els.soullinkMappingJson) return;
  try {
    state.soullinkMappingDraft = JSON.parse(els.soullinkMappingJson.value || "{}");
    state.soullinkMappingDirty = true;
    const applied = await previewSoullinkMapping({ adopt: true });
    if (applied) showToast("JSON 已载入并应用预览。");
  } catch (error) {
    showToast(`JSON 无效：${error.message || String(error)}`);
  }
}

async function copySoullinkMappingJson() {
  if (!state.soullinkMappingDraft) return;
  const text = JSON.stringify(state.soullinkMappingDraft, null, 2);
  try {
    await navigator.clipboard.writeText(text);
  } catch (_error) {
    if (!els.soullinkMappingJson) return;
    els.soullinkMappingJson.value = text;
    els.soullinkMappingJson.select();
    document.execCommand("copy");
  }
  showToast("高级映射 JSON 已复制。");
}

function syncSoullinkMappingJson() {
  if (!els.soullinkMappingJson || !state.soullinkMappingDraft) return;
  if (document.activeElement === els.soullinkMappingJson) return;
  els.soullinkMappingJson.value = JSON.stringify(state.soullinkMappingDraft, null, 2);
}

function renderSoullinkMappingChrome() {
  const validation = validateSoullinkMappingDraft();
  const data = state.soullinkMapping || {};
  if (els.soullinkMappingMode) {
    const isDefault = data.mode === "default" && !state.soullinkMappingDirty;
    els.soullinkMappingMode.textContent = state.soullinkMappingPreviewing
      ? "预览中"
      : (isDefault ? "跟随内置" : "自定义");
    els.soullinkMappingMode.className = `badge ${state.soullinkMappingPreviewing ? "live" : (isDefault ? "idle" : "ok")}`;
  }
  if (els.soullinkMappingStatus) {
    els.soullinkMappingStatus.textContent = validation.errors
      ? `${validation.errors} 个错误阻止预览与保存`
      : (state.soullinkMappingPreviewing
        ? "未保存映射正在实时预览"
        : (state.soullinkMappingDirty ? "映射已修改，等待预览" : `${validation.activeRules} 条规则已生效`));
  }
  if (els.soullinkMappingValidation) {
    const visibleIssues = validation.issues.slice(0, 6);
    els.soullinkMappingValidation.innerHTML = `
      <div class="mapping-validation-summary">${validation.activeRules} 条启用规则 · ${validation.errors} 个错误 · ${validation.warnings} 个提醒</div>
      ${visibleIssues.map((issue) => `<div class="mapping-validation-item is-${escapeHtml(issue.level)}">${escapeHtml(issue.message)}</div>`).join("")}
    `;
  }
  if (els.soullinkMappingSaveBtn) els.soullinkMappingSaveBtn.disabled = !state.soullinkMappingDirty || validation.errors > 0;
  if (els.soullinkMappingDiscardBtn) els.soullinkMappingDiscardBtn.hidden = !state.soullinkMappingPreviewing;
  if (els.soullinkMappingCaptureBtn) els.soullinkMappingCaptureBtn.disabled = !data.connected;
}

function validateSoullinkMappingDraft() {
  const draft = state.soullinkMappingDraft || { rules: [] };
  const inputs = new Map((state.soullinkMapping?.inputs || []).map((item) => [item.name, item]));
  const live2d = new Set((state.soullinkMapping?.live2d || []).map((item) => item.name));
  const issues = [];
  const targets = new Map();
  let activeRules = 0;
  (draft.rules || []).forEach((rule) => {
    if (!rule.enabled) return;
    activeRules += 1;
    if (!rule.source) issues.push({ ruleId: rule.id, level: "error", message: "缺少 Soullink 源通道" });
    if (!rule.target) {
      issues.push({ ruleId: rule.id, level: "error", message: "缺少 VTS 追踪输入" });
      return;
    }
    const sourceMin = Number(rule.sourceMin);
    const sourceNeutral = Number(rule.sourceNeutral);
    const sourceMax = Number(rule.sourceMax);
    if (![sourceMin, sourceNeutral, sourceMax].every(Number.isFinite) || sourceMin > sourceNeutral || sourceNeutral > sourceMax) {
      issues.push({ ruleId: rule.id, level: "error", message: "源锚点必须满足低位 ≤ 中性 ≤ 高位" });
    }
    const input = inputs.get(rule.target);
    if (!input) {
      issues.push({
        ruleId: rule.id,
        level: live2d.has(rule.target) ? "error" : "warning",
        message: live2d.has(rule.target)
          ? `${rule.target} 是只读 Live2D 输出，不能注入`
          : `${rule.target} 不在当前 VTS 输入目录，当前模型会安全跳过`,
      });
    } else {
      if (input.usedByModel === false) {
        issues.push({ ruleId: rule.id, level: "warning", message: `${rule.target} 可写，但当前模型未绑定输出` });
      }
      const anchors = [Number(rule.outputMin), Number(rule.outputNeutral), Number(rule.outputMax)];
      if (anchors.every(Number.isFinite) && (Math.min(...anchors) < Number(input.min) || Math.max(...anchors) > Number(input.max))) {
        issues.push({ ruleId: rule.id, level: "warning", message: `${rule.target} 的输出锚点超出模型输入范围` });
      }
    }
    if (!targets.has(rule.target)) targets.set(rule.target, []);
    targets.get(rule.target).push(rule);
  });
  targets.forEach((rules, target) => {
    if (rules.length > 1 && rules.slice(1).every((rule) => rule.blend === "replace")) {
      issues.push({ ruleId: rules.at(-1).id, level: "warning", message: `${target} 被多条 replace 规则占用，最后一条会覆盖前值` });
    }
  });
  return {
    activeRules,
    errors: issues.filter((item) => item.level === "error").length,
    warnings: issues.filter((item) => item.level === "warning").length,
    issues,
  };
}

function updateSoullinkMappingLiveValues(snapshot, parameters) {
  if (els.soullinkMappingWorkbench?.hidden || !state.soullinkMappingDraft) return;
  const facs = snapshot.live2dParams || snapshot.facs || {};
  const values = { ...(snapshot.facs || {}), ...facs };
  const composites = state.soullinkMappingDraft.composites || {};
  values.poseX = Number(values.headX || 0) + Number(values.bodyX || 0) * Number(composites.bodyXMix ?? 0.65);
  values.poseY = Number(values.headY || 0) + Number(values.bodyY || 0) * Number(composites.bodyYMix ?? 0.6);
  values.poseZ = Number(values.headZ || 0) + Number(values.bodyZ || 0) * Number(composites.bodyZMix ?? 0.65);
  const eyeOpen = Number(values.eyeOpen ?? 1);
  const eyeSquint = Number(values.eyeSquint || 0) * Number(composites.eyeSquintMix ?? 0.3);
  values.eyeOpenLeft = Math.max(0, eyeOpen * (1 - Number(values.eyeBlinkL || 0)) - eyeSquint);
  values.eyeOpenRight = Math.max(0, eyeOpen * (1 - Number(values.eyeBlinkR || 0)) - eyeSquint);
  values.mouthShape = Number(values.mouthSmile || 0) - Number(composites.mouthNeutral ?? 0.04)
    - Number(values.mouthFrown || 0) * Number(composites.mouthFrownMix ?? 1);
  values.browComposite = Number(values.browInnerUp || 0) * Number(composites.browInnerMix ?? 0.55)
    + Number(values.browOuterUp || 0) * Number(composites.browOuterMix ?? 0.45)
    - Number(values.browDown || 0) * Number(composites.browDownMix ?? 1);
  const vad = snapshot.vad || {};
  values.vadValence = Number(vad.current?.valence || 0);
  values.vadArousal = Number(vad.current?.arousal || 0);
  values.vadDominance = Number(vad.current?.dominance || 0);
  values.emotionIntensity = Number(vad.intensity || 0);
  const outputs = new Map(parameters.map((item) => [item.id, Number(item.value)]));
  state.soullinkMappingDraft.rules.forEach((rule) => {
    const sourceOutput = document.getElementById(`mapping-source-live-${rule.id}`);
    const targetOutput = document.getElementById(`mapping-target-live-${rule.id}`);
    if (sourceOutput) sourceOutput.value = Number.isFinite(Number(values[rule.source])) ? Number(values[rule.source]).toFixed(3) : "--";
    if (targetOutput) targetOutput.value = outputs.has(rule.target) ? outputs.get(rule.target).toFixed(3) : "--";
  });
}

function mappingNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? Number(number.toFixed(6)) : fallback;
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value || {}));
}

function boolText(value) {
  return value ? "开启" : "关闭";
}

function formatDuration(seconds) {
  const value = Number(seconds || 0);
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function formatTime(ts) {
  if (!ts) return "--";
  return new Date(Number(ts) * 1000).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function emptyText(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

function showToast(text) {
  if (!els.toast) return;
  els.toast.textContent = text;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 2600);
}

function requireSecondClick(button, key, message, nextText = "再次确认", timeoutMs = 6000) {
  const now = Date.now();
  const armed = button.dataset.confirmKey === key && now - Number(button.dataset.confirmAt || 0) < timeoutMs;
  if (armed) {
    delete button.dataset.confirmKey;
    delete button.dataset.confirmAt;
    return true;
  }
  button.dataset.confirmKey = key;
  button.dataset.confirmAt = String(now);
  button.dataset.originalText = button.dataset.originalText || button.textContent || "";
  button.textContent = nextText;
  showToast(message);
  window.clearTimeout(button._confirmTimer);
  button._confirmTimer = window.setTimeout(() => {
    if (button.dataset.confirmKey === key) {
      delete button.dataset.confirmKey;
      delete button.dataset.confirmAt;
      button.textContent = button.dataset.originalText || "";
      delete button.dataset.originalText;
    }
  }, timeoutMs);
  return false;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


