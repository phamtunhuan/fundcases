/* 私募基金监管处罚案例库 —— 零依赖前端逻辑 */
(function () {
  const $ = (s) => document.querySelector(s);
  const PAGE_SIZE = 25;
  let CASES = [], TEXTS = null, view = [], page = 1;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const state = {
    q: "", year: "", type: "", reg: "", region: "", doc: "", penalty: "", violation: "",
    sort: "date-desc", full: false
  };

  /* ============================================================
     搜索：全角归一 -> 去标点 -> 分词 -> 字段加权打分
     ============================================================ */
  const FULLWIDTH = /[\uFF01-\uFF5E\u3000]/g;
  function nfkc(s) {
    return String(s == null ? "" : s)
      .replace(FULLWIDTH, (ch) => ch === "\u3000" ? " "
        : String.fromCharCode(ch.charCodeAt(0) - 0xFEE0))
      .toLowerCase();
  }
  const PUNCT = /[\s\-–—_/\\|,，.。;；:：!！?？'"“”‘’()（）[\]【】{}《》〈〉、·~`@#$%^&*+=<>\u200b]/g;
  const sq = (s) => nfkc(s).replace(PUNCT, "");

  let IDX = [], FULLTEXT = null, fullLoading = false, fullTried = false;
  const IX_BY_ID = new Map();
  const IDXOf = (c) => IX_BY_ID.get(c.id);

  function buildIndex() {
    IX_BY_ID.clear();
    IDX = CASES.map((c) => {
      const nameRaw = [c.org_primary].concat(c.parties || []).join(" ");
      const metaRaw = [c.manager_type, c.manager_type_source, c.region, c.doc_type,
        (c.penalties || []).join(" "), (c.violation_tags || []).join(" "),
        c.legal_rep, c.register_no, c.member_type, c.year, c.date].join(" ");
      const bodyRaw = [c.penalty_text, c.decision_text].join(" ");
      return {
        name: sq(nameRaw), nameRaw,
        title: sq(c.title || ""), titleRaw: c.title || "",
        meta: sq(metaRaw), metaRaw,
        body: sq(bodyRaw), bodyRaw,
        full: ""
      };
    });
    CASES.forEach((c, i) => IX_BY_ID.set(c.id, IDX[i]));
  }

  /* 分词：空格/标点切分；英文引号或中文引号包裹的内容作为短语 */
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

  const W = { nameExact: 130, nameHead: 78, name: 48, title: 26, meta: 15, body: 8, full: 4 };

  function scoreToken(t, ix) {
    let s = 0;
    if (ix.name === t) s = W.nameExact;
    else if (ix.name.startsWith(t)) s = W.nameHead;
    else if (ix.name.includes(t)) s = W.name;
    if (ix.title.includes(t)) s = Math.max(s, W.title);
    if (ix.meta.includes(t)) s = Math.max(s, W.meta);
    if (ix.body.includes(t)) s = Math.max(s, W.body);
    if (ix.full && ix.full.includes(t)) s = Math.max(s, W.full);
    return s;
  }

  /* 纯中文长词的近似匹配：要求全部二字组在同一字段内命中，避免数字/英文误伤 */
  const CJK_ONLY = /^[\u4e00-\u9fa5]+$/;

  function approxHit(t, ix) {
    if (t.length < 4 || !CJK_ONLY.test(t)) return 0;
    const gs = [];
    for (let i = 0; i + 2 <= t.length; i++) gs.push(t.slice(i, i + 2));
    const fields = [ix.name, ix.title, ix.meta, ix.body, ix.full || ""];
    for (const f of fields) {
      if (!f) continue;
      const all = gs.every((g) => f.includes(g));
      if (all) return 0.6;      // 同一字段内二字组全覆盖，视为近似命中
    }
    return 0;
  }

  function searchScore(tokens, ix, qLen) {
    let total = 0;
    for (const t of tokens) {
      const s = scoreToken(t, ix);
      if (s) { total += s; continue; }
      const a = approxHit(t, ix);
      if (a) { total += 10 * a; continue; }
      return 0;   // AND 语义：任一条件不满足即淘汰
    }
    // 短语整体出现在机构名中，额外加权（如「上海高毅」）
    const phrase = tokens.join("");
    if (tokens.length > 1 && ix.name.includes(phrase)) total += 30;
    return total + Math.min(qLen, 12) * 0.01;
  }

  function loadFullText(cb) {
    if (FULLTEXT || fullLoading) return;
    fullLoading = true;
    const note = $("#result-count");
    if (note) note.textContent = "正在建立正文索引…";
    fetch("data/texts.json").then((r) => r.json()).then((d) => {
      FULLTEXT = {};
      Object.keys(d).forEach((k) => { FULLTEXT[k] = sq(d[k]); });
      IDX.forEach((ix, i) => { ix.full = FULLTEXT[String(CASES[i].id)] || ""; });
      fullLoading = false;
      cb();
    }).catch(() => { fullLoading = false; cb(); });
  }

  function uniq(vals) {
    return [...new Set(vals.filter(Boolean))].sort();
  }

  function fillSelect(el, values, label) {
    const cur = el.value;
    el.innerHTML = `<option value="">${label}</option>` +
      values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
    el.value = cur && values.includes(cur) ? cur : "";
  }

  /* 证监局设立地：4 直辖市 + 22 省 + 5 自治区 + 5 计划单列市 */
  const BUREAU_GROUPS = [
    ["直辖市", ["北京", "天津", "上海", "重庆"]],
    ["省", ["河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽",
            "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
            "四川", "贵州", "云南", "陕西", "甘肃", "青海"]],
    ["自治区", ["内蒙古", "广西", "西藏", "宁夏", "新疆"]],
    ["计划单列市", ["大连", "宁波", "厦门", "青岛", "深圳"]]
  ];

  function fillRegionSelect() {
    const el = $("#f-region");
    const cur = el.value;
    const present = new Set(CASES.map((c) => c.region).filter(Boolean));
    const html = [`<option value="">全部地区</option>`];
    BUREAU_GROUPS.forEach(([gname, list]) => {
      const items = list.filter((r) => present.has(r));
      if (!items.length) return;
      html.push(`<optgroup label="${gname}">`);
      items.forEach((r) => {
        const n = CASES.filter((c) => c.region === r).length;
        html.push(`<option value="${esc(r)}">${esc(r)}（${n}）</option>`);
      });
      html.push(`</optgroup>`);
    });
    // 兜底：若出现未归类的值也一并列出，避免数据遗漏被隐藏
    const rest = [...present].filter((r) => !BUREAU_GROUPS.some(([, l]) => l.includes(r)));
    if (rest.length) {
      html.push(`<optgroup label="未归类">`);
      rest.sort().forEach((r) => {
        const n = CASES.filter((c) => c.region === r).length;
        html.push(`<option value="${esc(r)}">${esc(r)}（${n}）</option>`);
      });
      html.push(`</optgroup>`);
    }
    el.innerHTML = html.join("");
    el.value = cur && present.has(cur) ? cur : "";
  }

  function initFilters() {
    const years = uniq(CASES.map((c) => c.year)).sort((a, b) => b - a);
    fillSelect($("#f-year"), years.map(String), "全部年份");
    fillSelect($("#f-type"), uniq(CASES.map((c) => c.manager_type)), "全部类型");
    fillRegionSelect();
    fillSelect($("#f-doc"), uniq(CASES.map((c) => c.doc_type)), "全部文书");
    fillSelect($("#f-penalty"), uniq(CASES.flatMap((c) => c.penalties)).sort(
      (a, b) => count(b, "penalties") - count(a, "penalties")), "全部措施");
    fillSelect($("#f-violation"), uniq(CASES.flatMap((c) => c.violation_tags)).sort(
      (a, b) => count(b, "violation_tags") - count(a, "violation_tags")), "全部事由");
  }

  const _cnt = {};
  function count(value, field) {
    const key = field + "|" + value;
    if (!(key in _cnt)) {
      _cnt[key] = CASES.filter((c) => {
        const v = c[field];
        return Array.isArray(v) ? v.includes(value) : v === value;
      }).length;
    }
    return _cnt[key];
  }

  let curTokens = [];
  const SCORE = new Map();

  function apply() {
    const rawQ = state.q.trim();
    curTokens = rawQ ? tokenize(rawQ) : [];

    // 勾选「全文」时先确保正文索引就绪
    if (curTokens.length && state.full && !FULLTEXT) { loadFullText(apply); return; }

    SCORE.clear();
    view = [];
    for (let i = 0; i < CASES.length; i++) {
      const c = CASES[i];
      if (state.year && String(c.year) !== state.year) continue;
      if (state.type && c.manager_type !== state.type) continue;
      if (state.reg) {
        if (state.reg === "__renamed") { if (!c.name_changed) continue; }
        else if (c.registry_status !== state.reg) continue;
      }
      if (state.region && c.region !== state.region) continue;
      if (state.doc && c.doc_type !== state.doc) continue;
      if (state.penalty && !c.penalties.includes(state.penalty)) continue;
      if (state.violation && !c.violation_tags.includes(state.violation)) continue;
      if (curTokens.length) {
        const s = searchScore(curTokens, IDX[i], rawQ.length);
        if (!s) continue;
        SCORE.set(c.id, s);
      }
      view.push(c);
    }

    // 元数据检索零命中时，自动加载一次全文索引再试
    if (curTokens.length && !view.length && !FULLTEXT && !fullTried) {
      fullTried = true;
      loadFullText(() => { fullTried = false; apply(); });
      return;
    }

    if (curTokens.length) {
      view.sort((a, b) => (SCORE.get(b.id) || 0) - (SCORE.get(a.id) || 0)
        || b.date.localeCompare(a.date));
      if (state.sort === "org") {
        view.sort((a, b) => (a.org_primary || "").localeCompare(b.org_primary || "", "zh"));
      }
    } else if (state.sort === "date-asc") view.sort((a, b) => a.date.localeCompare(b.date));
    else if (state.sort === "org") view.sort((a, b) => (a.org_primary || "").localeCompare(b.org_primary || "", "zh"));
    else view.sort((a, b) => b.date.localeCompare(a.date));

    page = 1;
    syncUrl();
    render();
  }

  /* 高亮：把命中的关键词包上 <mark>（对已转义的文本操作，尽力匹配） */
  function hl(raw, tokens) {
    let out = esc(raw);
    if (!tokens.length) return out;
    tokens.forEach((t) => {
      if (!t || t.length < 2) return;
      const pat = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try {
        out = out.replace(new RegExp(pat, "gi"), (m) => `<mark>${m}</mark>`);
      } catch (e) { /* 忽略非法正则 */ }
    });
    return out;
  }

  /* 摘要：命中正文时截取关键词上下文；优先展示「不在机构名里」的关键词 */
  function snippet(ix, tokens) {
    const raw = ix.bodyRaw || "";
    const rawLow = raw.toLowerCase();
    const text = ix.full || ix.body;
    if (!text && !raw) return "";
    const ordered = tokens.filter((t) => !ix.name.includes(t))
      .concat(tokens.filter((t) => ix.name.includes(t)));
    for (const t of ordered) {
      if (t.length < 2) continue;
      // 先在保留标点的原文里定位，摘要更易读
      const pr = rawLow.indexOf(t);
      if (pr >= 0 && raw) {
        const s = Math.max(0, pr - 30);
        const e = Math.min(raw.length, pr + t.length + 46);
        return (s > 0 ? "…" : "") + raw.slice(s, e).replace(/\s+/g, " ") + (e < raw.length ? "…" : "");
      }
      const pos = text.indexOf(t);
      if (pos < 0) continue;
      const start = Math.max(0, pos - 26);
      const end = Math.min(text.length, pos + t.length + 42);
      return (start > 0 ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
    }
    return "";
  }

  function render() {
    const pages = Math.max(1, Math.ceil(view.length / PAGE_SIZE));
    if (page > pages) page = pages;
    const mode = curTokens.length ? " · 按相关度排序" : "";
    $("#result-count").textContent =
      `命中 ${view.length} 例 · 第 ${page}/${pages} 页${mode}`;

    const rows = view.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((c) => {
      const tcls = c.manager_type.startsWith("私募证券") ? "type-sec"
        : c.manager_type.startsWith("私募股权") ? "type-eq" : "type-na";
      const name = c.org_primary || c.parties[0] || c.title;
      const sub = c.parties.length > 1 ? c.parties.slice(1).join("、") : "";
      const ix = IDXOf(c);
      const snip = curTokens.length && ix ? snippet(ix, curTokens) : "";
      return `<tr>
        <td>${esc(c.date)}</td>
        <td><span class="org" data-id="${c.id}">${hl(name, curTokens)}</span>
          <span class="reg-badge ${c.registry_status === "已注销" ? "reg-off" : "reg-on"}">${esc(c.registry_status)}</span>
          ${c.name_changed ? '<span class="reg-badge reg-off" title="协会在册/注销两处均无该名称，推定已更名">已更名</span>' : ""}
          ${sub ? `<div class="sub2">其他当事人：${esc(sub)}</div>` : ""}
          <div class="sub2">${esc(c.doc_type)}</div>
          ${snip ? `<div class="snip">${hl(snip, curTokens)}</div>` : ""}</td>
        <td class="${tcls}">${esc(c.manager_type)}</td>
        <td>${esc(c.region || "—")}</td>
        <td>${c.penalties.length ? c.penalties.map((p) => `<span class="tag red">${esc(p)}</span>`).join("") : '<span class="tag grey">—</span>'}</td>
        <td>${c.violation_tags.map((v) => `<span class="tag">${esc(v)}</span>`).join("") || '<span class="tag grey">—</span>'}</td>
        <td><a href="${esc(c.source_url)}" target="_blank" rel="noopener">${c.doc_format === "pdf" ? "PDF" : "网页"} ↗</a></td>
      </tr>`;
    }).join("");
    $("#case-tbody").innerHTML = rows ||
      `<tr><td colspan="7" style="text-align:center;color:#8492a6;padding:26px;line-height:1.8">
        ${curTokens.length
          ? `没有匹配「${esc(state.q.trim())}」的案例。<br>
             已检索机构名、当事人、登记编号、处分措施、违规事由与决定理由${FULLTEXT ? "及正文全文" : ""}；
             可减少关键词、去掉年份等限定，或勾选「全文」再试。`
          : "没有匹配的案例，试试放宽筛选条件"}
       </td></tr>`;

    const pagerHtml = (id) => {
      const pages = Math.max(1, Math.ceil(view.length / PAGE_SIZE));
      if (pages <= 1) return "";
      let btns = "";
      const push = (p, label) => btns +=
        `<button data-p="${p}" class="${p === page ? "cur" : ""}" ${p === page ? "disabled" : ""}>${label}</button>`;
      push(1, "首页");
      push(Math.max(1, page - 1), "上一页");
      const from = Math.max(1, Math.min(page - 2, pages - 4));
      const to = Math.min(pages, from + 4);
      for (let p = from; p <= to; p++) push(p, String(p));
      push(Math.min(pages, page + 1), "下一页");
      push(pages, "末页");
      return `<span>共 ${view.length} 例</span>` + btns;
    };
    $("#pager").innerHTML = pagerHtml();
    $("#pager2").innerHTML = pagerHtml();
    document.querySelectorAll(".pager button").forEach((b) =>
      b.onclick = () => { page = +b.dataset.p; render(); window.scrollTo({ top: $("#browse").offsetTop - 10, behavior: "smooth" }); });

    renderChips();
  }

  function renderChips() {
    const labels = { year: "年份", type: "类型", reg: "登记状态", region: "地区", doc: "文书", penalty: "措施", violation: "事由", q: "关键词" };
    const items = Object.entries(state)
      .filter(([k, v]) => v && k !== "sort" && k !== "full")
      .map(([k, v]) =>
        `<span class="chip">${labels[k]}：${esc(v)} <b data-k="${k}" style="cursor:pointer;color:#b8322c">×</b></span>`);
    if (state.full) items.push('<span class="chip">检索范围：含正文全文</span>');
    $("#active-filters").innerHTML = items.join("") +
      (items.length ? `<span class="chip" id="clear-all" style="cursor:pointer;background:#fdf0ef;border-color:#f6dfdd;color:#b8322c">清空全部 ×</span>` : "");
    document.querySelectorAll("#active-filters b").forEach((b) =>
      b.onclick = () => { state[b.dataset.k] = ""; syncInputs(); apply(); });
    const ca = $("#clear-all");
    if (ca) ca.onclick = () => {
      Object.keys(state).forEach((k) => {
        if (k === "full") state.full = false;
        else if (k !== "sort") state[k] = "";
      });
      syncInputs(); apply();
    };
  }

  function syncInputs() {
    $("#q").value = state.q; $("#f-year").value = state.year;
    $("#f-type").value = state.type; $("#f-reg").value = state.reg; $("#f-region").value = state.region;
    $("#f-doc").value = state.doc; $("#f-penalty").value = state.penalty;
    $("#f-violation").value = state.violation;
    $("#f-full").checked = !!state.full;
  }

  function renderStats() {
    const sec = CASES.filter((c) => c.manager_type.startsWith("私募证券")).length;
    const eq = CASES.filter((c) => c.manager_type.startsWith("私募股权")).length;
    const reg = CASES.filter((c) => c.registry_status === "在册" || c.registry_status === "已注销").length;
    const regions = uniq(CASES.map((c) => c.region).filter(Boolean)).length;
    const years = CASES.map((c) => c.year);
    const stats = [
      ["案例总数", CASES.length],
      ["私募证券类", sec],
      ["私募股权创业类", eq],
      ["协会公示匹配", reg],
      ["覆盖地区", regions],
      ["时间跨度", Math.min(...years) + "–" + Math.max(...years)]
    ];
    $("#stat-row").innerHTML = stats.map(([l, n]) =>
      `<div class="stat"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");
    $("#total-count").textContent = CASES.length;
    if (CASES.length) $("#update-date").textContent = CASES[0].date;
  }

  function renderCharts() {
    const byYear = {};
    CASES.forEach((c) => { byYear[c.year] = (byYear[c.year] || 0) + 1; });
    const ys = Object.keys(byYear).map(Number).sort();
    const max = Math.max(...Object.values(byYear));
    $("#year-chart").innerHTML = ys.map((y) => `
      <div class="col" title="${y}年 ${byYear[y]} 例">
        <div class="v">${byYear[y]}</div>
        <div class="bar" style="height:${Math.max(4, byYear[y] / max * 118)}px"></div>
        <div class="k">${String(y).slice(2)}</div>
      </div>`).join("");

    const hbars = (el, pairs, cls) => {
      const m = Math.max(...pairs.map((p) => p[1]), 1);
      $(el).innerHTML = pairs.map(([name, n]) => `
        <div class="h-bar">
          <div class="name" title="${esc(name)}">${esc(name)}</div>
          <div class="track"><div class="fill ${cls || ""}" style="width:${n / m * 100}%"></div></div>
          <div class="num">${n}</div>
        </div>`).join("");
    };
    const tally = (field) => {
      const m = {};
      CASES.forEach((c) => c[field].forEach((t) => { m[t] = (m[t] || 0) + 1; }));
      return Object.entries(m).sort((a, b) => b[1] - a[1]);
    };
    hbars("#penalty-chart", tally("penalties").slice(0, 10), "blue");
    hbars("#violation-chart", tally("violation_tags").slice(0, 10));
  }

  /* 地址栏同步，便于分享检索结果 */
  let urlTimer = null;
  function syncUrl() {
    clearTimeout(urlTimer);
    urlTimer = setTimeout(() => {
      const p = new URLSearchParams();
      if (state.q.trim()) p.set("q", state.q.trim());
      ["year", "type", "reg", "region", "doc", "penalty", "violation"].forEach((k) => {
        if (state[k]) p.set(k, state[k]);
      });
      if (state.full) p.set("full", "1");
      const qs = p.toString();
      const url = location.pathname + (qs ? "?" + qs : "") + location.hash;
      try { history.replaceState(null, "", url); } catch (e) { /* 忽略 */ }
    }, 260);
  }

  function readUrl() {
    const p = new URLSearchParams(location.search);
    if (p.get("q")) { state.q = p.get("q"); $("#q").value = state.q; }
    ["year", "type", "reg", "region", "doc", "penalty", "violation"].forEach((k) => {
      if (p.get(k)) {
        state[k] = p.get(k);
        const el = $(`#f-${k}`);
        if (el) el.value = state[k];
      }
    });
    if (p.get("full") === "1") { state.full = true; $("#f-full").checked = true; }
  }

  function bind() {
    let t = null;
    $("#q").addEventListener("input", (e) => {
      state.q = e.target.value;
      clearTimeout(t);
      t = setTimeout(apply, 170);      // 输入防抖，避免逐字全表扫描
    });
    $("#q").addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.target.value = ""; state.q = ""; apply(); }
    });
    $("#f-full").addEventListener("change", (e) => {
      state.full = e.target.checked;
      if (state.full) loadFullText(apply); else apply();
    });
    $("#clear-q").onclick = () => {
      $("#q").value = ""; state.q = "";
      ["year", "type", "reg", "region", "doc", "penalty", "violation"].forEach((k) => {
        state[k] = ""; const el = $(`#f-${k}`); if (el) el.value = "";
      });
      apply();
    };
    [["#f-year", "year"], ["#f-type", "type"], ["#f-reg", "reg"],
     ["#f-region", "region"],
     ["#f-doc", "doc"], ["#f-penalty", "penalty"], ["#f-violation", "violation"],
     ["#f-sort", "sort"]].forEach(([sel, key]) =>
      $(sel).addEventListener("change", (e) => { state[key] = e.target.value; apply(); }));

    // 按 / 快速聚焦搜索框
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement !== $("#q")) {
        e.preventDefault(); $("#q").focus();
      }
    });

    $("#case-tbody").addEventListener("click", (e) => {
      const el = e.target.closest(".org");
      if (el) openModal(+el.dataset.id);
    });
    $("#m-close").onclick = () => { $("#modal").hidden = true; };
    $("#modal").addEventListener("click", (e) => {
      if (e.target.id === "modal") $("#modal").hidden = true;
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") $("#modal").hidden = true;
    });
  }

  function openModal(id) {
    const c = CASES.find((x) => x.id === id);
    if (!c) return;
    $("#m-title").textContent = c.title;
    const reg = c.registry_status
      ? `<span class="reg-badge ${c.registry_status === "已注销" ? "reg-off" : "reg-on"}">协会公示·${esc(c.registry_status)}</span>`
      : "";
    const renamed = c.name_changed
      ? `<span class="reg-badge reg-off" title="协会在册/注销两处均无该名称记录，推定管理人已变更名称">原名查无·已变更名称</span>`
      : "";
    $("#m-meta").innerHTML = [
      `发布日期：${esc(c.date)}`, `文书类型：${esc(c.doc_type)}`,
      `管理人类型：${esc(c.manager_type)}（${esc(c.manager_type_source)}）`,
      `地区：${esc(c.region || "未识别")}`,
      c.register_no ? `登记编号：${esc(c.register_no)}` : "",
      c.legal_rep ? `法定代表人：${esc(c.legal_rep)}` : "",
      c.member_type ? `会员类型：${esc(c.member_type)}` : "",
      c.penalties.length ? `处分：${esc(c.penalties.join("、"))}` : "",
      c.violation_tags.length ? `事由：${esc(c.violation_tags.join("、"))}` : "",
      `当事人：${esc(c.parties.join("、") || "—")}`
    ].filter(Boolean).map((t) => `<span>${t}</span>`).join("") + reg + renamed;
    $("#m-link").href = c.source_url;
    const regLink = $("#m-reg");
    if (c.registry_url) { regLink.hidden = false; regLink.href = c.registry_url; }
    else regLink.hidden = true;
    $("#m-text").textContent = "正文加载中…";
    $("#m-penalty").innerHTML = c.penalty_text
      ? `<div class="pbox"><div class="ptitle">处分决定原文（用于核对措施标注）</div>
           <div class="ptext">${esc(c.penalty_text)}</div></div>`
      : "";
    $("#modal").hidden = false;

    const show = (t) => {
      const body = (t || "").trim();
      if (!body) {
        $("#m-text").textContent = "（该案例正文为空，请点击查看协会原文）";
        return;
      }
      if (curTokens.length) {
        const box = $("#m-text");
        box.innerHTML = hl(body, curTokens);
        box.scrollTop = 0;
        const m = box.querySelector("mark");
        if (m) {                     // 定位到第一个命中词
          const rb = m.getBoundingClientRect();
          const bb = box.getBoundingClientRect();
          box.scrollTop += rb.top - bb.top - 80;
        }
      } else $("#m-text").textContent = body;
    };
    if (TEXTS) return show(TEXTS[String(id)]);
    fetch("data/texts.json").then((r) => r.json()).then((d) => {
      TEXTS = d; show(d[String(id)]);
    }).catch(() => show("正文加载失败，请点击查看协会原文。"));
  }

  fetch("data/cases.json").then((r) => r.json()).then((d) => {
    CASES = d;
    buildIndex();
    initFilters(); renderStats(); renderCharts(); bind(); readUrl(); apply();
  }).catch((e) => {
    $("#case-tbody").innerHTML =
      `<tr><td colspan="7" style="text-align:center;padding:26px;color:#b8322c">
      数据加载失败（${esc(e.message)}）。本站需通过 HTTP 访问（如 GitHub Pages 或本地静态服务器），
      直接用 file:// 打开会被浏览器安全策略拦截。</td></tr>`;
  });
})();
