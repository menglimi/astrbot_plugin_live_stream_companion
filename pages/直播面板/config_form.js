const LiveConfigForm = (() => {
  function renderGroups(container, groups, schema, values, options = {}) {
    const includeGroup = options.includeGroup || (() => true);
    const includeKey = options.includeKey || (() => true);
    const dynamic = options.dynamic || {};
    container.innerHTML = groups
      .filter(includeGroup)
      .map((group) => {
        const keys = (group.keys || []).filter((key) => includeKey(key, group));
        if (!keys.length) return "";
        return `
          <article class="config-card" data-group="${escapeHtml(group.id)}">
            <div class="config-card-head">
              <div>
                <h2>${escapeHtml(group.title)}</h2>
                <p>${escapeHtml(group.description || "")}</p>
              </div>
            </div>
            <div class="field-grid">
              ${keys.map((key) => renderField(key, schema[key], values[key], dynamic)).join("")}
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderField(key, meta = {}, value, dynamic = {}) {
    const type = meta.type || "string";
    const label = meta.description || key;
    const hint = meta.hint || "";
    const id = `cfg-${key}`;
    const slider = meta.slider || {};
    const staticOptions = meta.options || defaultOptionsForKey(key);
    const choices = buildChoices(key, staticOptions, dynamic, value ?? meta.default ?? "");
    const options = choices.map((item) => item.value);
    const current = value ?? meta.default ?? "";
    if (key === "soullink_vts_mapping") {
      return `
        <div class="field field-wide mapping-config-link">
          <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
          <button type="button" data-open-soullink-mapping>打开高级参数校准</button>
        </div>
      `;
    }
    if (type === "bool") {
      return `
        <label class="field field-toggle" data-config-key="${escapeHtml(key)}" for="${escapeHtml(id)}">
          <span>
            <b>${escapeHtml(label)}</b>
            ${hint ? `<small>${escapeHtml(hint)}</small>` : ""}
          </span>
          <input id="${escapeHtml(id)}" class="config-control" name="${escapeHtml(key)}" type="checkbox" ${current ? "checked" : ""}>
        </label>
      `;
    }
    if (type === "text") {
      return `
        <label class="field field-wide" data-config-key="${escapeHtml(key)}" for="${escapeHtml(id)}">
          <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
          <textarea id="${escapeHtml(id)}" class="config-control" name="${escapeHtml(key)}" rows="4">${escapeHtml(current)}</textarea>
        </label>
      `;
    }
    if (options.length) {
      const select = `
          <select id="${escapeHtml(id)}" class="config-control" name="${escapeHtml(key)}" data-dynamic-select="${choices.some((item) => item.dynamic) ? "1" : "0"}">
            ${choices.map((item) => `<option value="${escapeHtml(item.value)}" ${String(current) === String(item.value) ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}
          </select>`;
      const actions = dynamicActionsForKey(key, dynamic);
      if (!actions.length) {
        return `
        <label class="field" data-config-key="${escapeHtml(key)}" for="${escapeHtml(id)}">
          <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
          ${select}
        </label>
      `;
      }
      return `
        <div class="field field-wide" data-config-key="${escapeHtml(key)}">
          <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
          <div class="field-actions">${select}${actions}</div>
          <small class="field-note" data-config-note="${escapeHtml(key)}"></small>
        </div>
      `;
    }
    if (isColorKey(key)) {
      const safeColor = /^#[0-9a-f]{6}$/i.test(String(current)) ? current : "#ffffff";
      return `
        <label class="field" data-config-key="${escapeHtml(key)}" for="${escapeHtml(id)}">
          <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
          <input id="${escapeHtml(id)}" class="config-control color-control" name="${escapeHtml(key)}" type="color" value="${escapeHtml(safeColor)}">
        </label>
      `;
    }
    if (type === "int" || type === "float") {
      const step = slider.step ?? (type === "float" ? 0.1 : 1);
      return `
        <label class="field" data-config-key="${escapeHtml(key)}" for="${escapeHtml(id)}">
          <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
          <input id="${escapeHtml(id)}" class="config-control" name="${escapeHtml(key)}" type="number"
            value="${escapeHtml(current)}" step="${escapeHtml(step)}"
            ${slider.min !== undefined ? `min="${escapeHtml(slider.min)}"` : ""}
            ${slider.max !== undefined ? `max="${escapeHtml(slider.max)}"` : ""}>
        </label>
      `;
    }
    const fallbackActions = dynamicActionsForKey(key, dynamic);
    const textInput = `<input id="${escapeHtml(id)}" class="config-control" name="${escapeHtml(key)}" type="text" value="${escapeHtml(current)}">`;
    if (fallbackActions) {
      return `
        <div class="field field-wide" data-config-key="${escapeHtml(key)}">
          <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
          <div class="field-actions">${textInput}${fallbackActions}</div>
          <small class="field-note" data-config-note="${escapeHtml(key)}"></small>
        </div>
      `;
    }
    return `
      <label class="field" data-config-key="${escapeHtml(key)}" for="${escapeHtml(id)}">
        <span><b>${escapeHtml(label)}</b>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</span>
        ${textInput}
      </label>
    `;
  }

  function collectValues(container, schema, fallbackValues = {}) {
    const values = { ...fallbackValues };
    container?.querySelectorAll(".config-control").forEach((control) => {
      const meta = schema[control.name] || {};
      if (meta.type === "bool") {
        values[control.name] = control.checked;
      } else if (meta.type === "int") {
        values[control.name] = Number.parseInt(control.value || "0", 10);
      } else if (meta.type === "float") {
        values[control.name] = Number.parseFloat(control.value || "0");
      } else {
        values[control.name] = control.value;
      }
    });
    return values;
  }

  function defaultValues(schema) {
    return Object.fromEntries(Object.entries(schema).map(([key, meta]) => [key, meta.default]));
  }

  const DYNAMIC_FIELD_SOURCES = {
    vts_host: "vtsCandidates",
    live_tts_external_tool_name: "externalTts",
    live_tts_external_service_method: "ttsMethods",
  };

  function buildChoices(key, staticOptions, dynamic, current) {
    const items = [];
    const push = (value, label, isDynamic) => {
      const text = value === undefined || value === null ? "" : String(value);
      if (!text) return;
      if (items.some((item) => item.value === text)) return;
      items.push({ value: text, label: label || text, dynamic: Boolean(isDynamic) });
    };
    const source = DYNAMIC_FIELD_SOURCES[key];
    const dynamicList = source ? dynamic[source] || [] : [];
    if (dynamicList.length) {
      dynamicList.forEach((entry) => {
        if (entry && typeof entry === "object") {
          push(entry.value ?? entry.host ?? entry.tool ?? entry.port, entry.label, true);
        } else {
          push(entry, methodLabel(entry), true);
        }
      });
    }
    (staticOptions || []).forEach((item) => push(item, optionLabelForKey(key, item)));
    if (String(current || "").trim() && !items.some((item) => item.value === String(current))) {
      push(String(current), `${current}（当前值）`);
    }
    if (items.length) {
      items.push({ value: "__custom__", label: "自定义（手动填写）…", dynamic: false });
    }
    return items;
  }

  function dynamicActionsForKey(key, dynamic) {
    if (key === "vts_host") {
      const label = dynamic.vtsScanning ? "扫描中…" : "扫描局域网";
      return `<button type="button" data-action="scan-vts" ${dynamic.vtsScanning ? "disabled" : ""}>${label}</button>`;
    }
    if (key === "live_tts_external_tool_name") {
      const label = dynamic.ttsRefreshing ? "刷新中…" : "刷新列表";
      return `<button type="button" data-action="refresh-tts" ${dynamic.ttsRefreshing ? "disabled" : ""}>${label}</button>`;
    }
    return "";
  }

  function methodLabel(value) {
    return optionLabelForKey("live_tts_external_service_method", value);
  }

  function defaultOptionsForKey(key) {
    const options = {
      bilibili_type: ["web", "laplace", "open_live"],
      bili_live_auto_reply_mode: ["native", "direct"],
      subtitle_scope: ["bili_live", "twitch_live", "live", "all"],
      subtitle_position: ["bottom", "center", "top"],
      mouth_sync_mode: ["set", "add"],
      soullink_mode: ["emotion", "full"],
      soullink_motion_style: ["natural", "lively", "calm", "shy"],
    };
    return options[key] || [];
  }

  function optionLabelForKey(key, value) {
    const labels = {
      bilibili_type: { web: "Web 直播间", laplace: "Laplace 桥接", open_live: "B站开放平台" },
      bili_live_auto_reply_mode: { native: "AstrBot 原生流程", direct: "直接调用模型" },
      live_tts_backend: { astrbot_provider: "AstrBot 会话 TTS", registered_service: "外部注册服务", auto: "外部优先，失败自动回退" },
      live_tts_external_service_method: { text_to_speech: "text_to_speech（直接返回音频路径）", render_pcm_wav: "render_pcm_wav（生成本地 WAV，可同步嘴型）" },
      subtitle_scope: { bili_live: "仅 B站直播", twitch_live: "仅 Twitch 直播", live: "全部直播来源", all: "所有 Bot 回复" },
      subtitle_position: { bottom: "底部", center: "中部", top: "顶部" },
      mouth_sync_mode: { set: "覆盖参数", add: "叠加参数" },
      soullink_mode: { emotion: "情绪表演", full: "完整表演" },
      soullink_motion_style: { natural: "自然", lively: "活泼", calm: "平静", shy: "害羞" },
    };
    return labels[key]?.[value] || value;
  }

  function isColorKey(key) {
    return key.endsWith("_color");
  }

  return {
    collectValues,
    defaultValues,
    renderGroups,
  };
})();
