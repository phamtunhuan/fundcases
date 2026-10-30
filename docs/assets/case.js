/* 处罚案例详情页 —— 零依赖 */
(function () {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const P = new URLSearchParams(location.search);
  const id = parseInt(P.get("id") || "", 10);
  const qRaw = (P.get("q") || "").trim();

  /* 关键词归一与高亮：与列表页保持一致 */
  const FULLWIDTH = /[\uFF01-\uFF5E\u3000]/g;
  const nfkc = (s) => String(s == null ? "" : s)
    .replace(FULLWIDTH, (ch) => ch === "\u3000" ? " "
      : String.fromCharCode(ch.charCodeAt(0) - 0xFEE0)).toLowerCase();
  const PUNCT = /[\s\-–—_/\\|,，.。;；:：!！?？'"“”‘’()（）[\]【】{}《》〈〉、·~`@#$%^&*+=<>\u200b]/g;
  const sq = (s) => nfkc(s).replace(PUNCT, "");

  function tokenize(q) {
    const out = [];
    const re = /"([^"]+)"|“([^”]+)”|‘([^’]+)’|(\S+)/g;
    let m;
    while ((m = re.exec(q))) {
      const t = sq(m[1] || m[2] || m[3] || m[4] || "");
      if (t) out.push(t);
    }
    return out;
  }
  const TOKENS = qRaw ? tokenize(qRaw) : [];

  function hl(raw) {
    let out = esc(raw);
    TOKENS.forEach((t) => {
      if (!t || t.length < 2) return;
      const pat = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try { out = out.replace(new RegExp(pat, "gi"), (m) => `<mark>${m}</mark>`); }
      catch (e) { /* ignore */ }
    });
    return out;
  }

  function kvRow(k, v, cls) {
    if (v === "" || v == null || v === "—") return "";
    return `<div class="kv-row"><dt>${esc(k)}</dt><dd class="${cls || ""}">${v}</dd></div>`;
  }

  function badges(c) {
    const out = [];
    if (c.registry_status) {
      out.push(`<span class="reg-badge ${c.registry_status === "已注销" ? "reg-off" : "reg-on"}">协会公示·${esc(c.registry_status)}</span>`);
    }
    if (c.name_changed) {
      out.push(`<span class="reg-badge reg-off" title="协会在册、注销两处公示均无该名称，推定管理人已变更名称">原名查无·已更名</span>`);
    }
    if (c.doc_format) out.push(`<span class="reg-badge doc-badge">${c.doc_format === "pdf" ? "扫描件" : "网页原文"}</span>`);
    if (c.batch_notice) out.push(`<span class="reg-badge doc-badge" title="该公告一次性注销多家机构，不归属单一管理人">批量公告</span>`);
    if (c.title_truncated) out.push(`<span class="reg-badge doc-badge">标题截断</span>`);
    return out.join("");
  }

  function notFound(msg) {
    $("#root").innerHTML = `<div class="panel empty-state">
      <h2>${esc(msg)}</h2>
      <p>请从案例库中选择一条案例，或检查链接中的编号是否正确。</p>
      <p><a class="btn" href="index.html">返回案例库</a></p>
    </div>`;
  }

  let CURRENT_TEXT = "";

  function render(c, all) {
    const name = c.org_primary || (c.parties && c.parties[0]) || c.title || "（未识别机构）";
    document.title = `${name} · 处罚案例 | 私募基金监管处罚案例库`;

    const meta = [
      ["发布日期", c.date], ["文书类型", c.doc_type], ["地区", c.region || "未识别"],
      ["管理人类型", c.manager_type], ["年度", c.year + " 年"]
    ];

    const penalties = (c.penalties || []);
    const violations = (c.violation_tags || []);
    const parties = (c.parties || []);
    const others = parties.filter((p) => p !== name);

    const penaltyText = (c.penalty_text || "").trim();
    const decisionText = (c.decision_text || "").trim();

    const regRows = [
      kvRow("登记编号", c.register_no ? esc(c.register_no) : ""),
      kvRow("法定代表人", c.legal_rep ? esc(c.legal_rep) : ""),
      kvRow("会员类型", c.member_type ? esc(c.member_type) : ""),
      kvRow("备案基金数", c.fund_count != null && c.fund_count !== "" ? esc(c.fund_count) : ""),
      kvRow("类型来源", c.manager_type_source ? esc(c.manager_type_source) : "")
    ].join("");

    const sideRows = [
      kvRow("案例编号", `#${c.id}`),
      kvRow("发布日期", esc(c.date)),
      kvRow("文书类型", esc(c.doc_type)),
      kvRow("地区", esc(c.region || "未识别")),
      kvRow("管理人类型", esc(c.manager_type)),
      kvRow("登记状态", c.registry_status ? esc(c.registry_status) : ""),
      kvRow("当事人", esc(parties.join("、") || "—")),
      kvRow("正文字数", c.text_length ? esc(c.text_length) : "")
    ].join("");

    // 上一条 / 下一条（按日期倒序排列后的相邻项）
    const sorted = all.slice().sort((a, b) => b.date.localeCompare(a.date));
    const idx = sorted.findIndex((x) => x.id === c.id);
    const prev = idx > 0 ? sorted[idx - 1] : null;
    const next = idx >= 0 && idx < sorted.length - 1 ? sorted[idx + 1] : null;
    const qs = qRaw ? `&q=${encodeURIComponent(qRaw)}` : "";
    const navHtml = `
      ${prev ? `<a class="nav-link prev" href="case.html?id=${prev.id}${qs}">← 上一条：${esc(prev.org_primary || prev.title).slice(0, 18)}</a>` : "<span></span>"}
      ${next ? `<a class="nav-link next" href="case.html?id=${next.id}${qs}">下一条：${esc(next.org_primary || next.title).slice(0, 18)} →</a>` : "<span></span>"}`;

    $("#root").innerHTML = `
      <nav class="crumb">
        <a href="index.html">案例库</a><span class="sep">/</span>
        <span>${esc(c.doc_type)}</span><span class="sep">/</span>
        <b>${esc(name)}</b>
      </nav>

      <article class="case-layout">
        <div class="case-main">
          <div class="case-head">
            <h1>${hl(name)}</h1>
            <div class="badge-row">${badges(c)}</div>
            <p class="case-sub">${esc(c.title)}</p>
          </div>

          <div class="meta-strip">
            ${meta.map(([k, v]) => `<div class="meta-item"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("")}
          </div>

          ${others.length ? `<p class="other-parties">其他当事人：${esc(others.join("、"))}</p>` : ""}

          <section class="panel">
            <div class="panel-head"><h2>处分措施</h2><span class="hint">依据决定主文自动标注</span></div>
            <div class="tag-row">
              ${penalties.length ? penalties.map((p) => `<span class="tag red big">${esc(p)}</span>`).join("")
                : '<span class="tag grey">未识别到明确处分措施，请核对原文</span>'}
            </div>
          </section>

          <section class="panel">
            <div class="panel-head"><h2>违规事由</h2><span class="hint">正文关键词自动标注，仅供参考</span></div>
            <div class="tag-row">
              ${violations.length ? violations.map((v) => `<span class="tag big">${esc(v)}</span>`).join("")
                : '<span class="tag grey">未识别到违规事由标签</span>'}
            </div>
          </section>

          ${penaltyText || decisionText ? `
          <section class="panel">
            <div class="panel-head"><h2>处分决定原文摘录</h2><span class="hint">用于核对措施与事由标注</span></div>
            ${penaltyText ? `<blockquote class="quote">${hl(penaltyText)}</blockquote>` : ""}
            ${decisionText ? `<details class="decision"><summary>查看决定主文段落</summary><pre class="doc small">${hl(decisionText)}</pre></details>` : ""}
          </section>` : ""}

          <section class="panel">
            <div class="panel-head">
              <h2>决定书全文</h2>
              <div class="doc-tools">
                <span class="hint">${c.doc_format === "pdf" ? "扫描件经 OCR 识别，可能存在误差" : "网页原文"}</span>
                <button class="btn-s" id="btn-copy" type="button">复制正文</button>
              </div>
            </div>
            <pre class="doc" id="doc">正文加载中…</pre>
          </section>

          <nav class="case-nav">${navHtml}</nav>
        </div>

        <aside class="case-side">
          <section class="panel sticky">
            <div class="panel-head"><h2>案例要素</h2></div>
            <dl class="kv">${sideRows}</dl>
          </section>

          <section class="panel">
            <div class="panel-head"><h2>机构登记信息</h2><span class="hint">协会公示</span></div>
            ${regRows ? `<dl class="kv">${regRows}</dl>` : '<p class="hint">未匹配到协会公示登记记录，机构可能已更名或非私募管理人。</p>'}
            ${c.registry_url ? `<a class="side-link" href="${esc(c.registry_url)}" target="_blank" rel="noopener">查看协会公示信息 ↗</a>` : ""}
          </section>

          <section class="panel">
            <div class="panel-head"><h2>原始出处</h2></div>
            <div class="side-links">
              <a class="side-link" href="${esc(c.source_url)}" target="_blank" rel="noopener">协会原文（${esc((c.doc_format || "").toUpperCase() || "网页")}）↗</a>
              <a class="side-link" href="index.html">返回案例库列表</a>
            </div>
          </section>
        </aside>
      </article>`;

    // 复制正文
    const btn = $("#btn-copy");
    if (btn) {
      btn.onclick = () => {
        const body = CURRENT_TEXT || "";
        if (navigator.clipboard && body) {
          navigator.clipboard.writeText(body).then(() => {
            btn.textContent = "已复制"; setTimeout(() => (btn.textContent = "复制正文"), 1500);
          }).catch(() => { btn.textContent = "复制失败"; });
        }
      };
    }


    // 返回链接带上来源列表的筛选条件
    try {
      const last = sessionStorage.getItem("fundcases:listUrl");
      if (last && last.indexOf("index.html") !== -1) $("#back-link").href = last;
    } catch (e) { /* ignore */ }
  }

  if (!id && id !== 0) { notFound("未指定案例编号"); return; }

  function fillDoc(text) {
    const box = $("#doc");
    if (!box) return;
    CURRENT_TEXT = text || "";
    if (!CURRENT_TEXT) {
      box.textContent = "（该案例正文为空，请点击「查看协会原文」）";
      return;
    }
    box.innerHTML = hl(CURRENT_TEXT);
    // 命中词定位
    if (TOKENS.length) {
      const m = box.querySelector("mark");
      if (m) {
        const rb = m.getBoundingClientRect();
        const bb = box.getBoundingClientRect();
        window.scrollTo({ top: window.scrollY + rb.top - bb.top - 120, behavior: "smooth" });
      }
    }
  }

  function loadText(c) {
    fetch("data/texts.json").then((r) => r.json()).then((d) => {
      fillDoc(d[String(c.id)] || "");
    }).catch(() => fillDoc(""));
  }

  fetch("data/cases.json").then((r) => r.json()).then((cases) => {
    const c = cases.find((x) => x.id === id);
    if (!c) { notFound("未找到该案例"); return; }
    render(c, cases);          // 先渲染要素，正文留占位
    loadText(c);               // 再异步取全文
  }).catch((e) => {
    notFound("数据加载失败");
    const l = $("#loading"); if (l) l.textContent = String((e && e.message) || e);
  });
})();
