/* 私募基金监管处罚案例库 —— 零依赖前端逻辑 */
(function () {
  const $ = (s) => document.querySelector(s);
  const PAGE_SIZE = 25;
  let CASES = [], TEXTS = null, view = [], page = 1;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const state = {
    q: "", year: "", type: "", region: "", doc: "", penalty: "", violation: "", sort: "date-desc"
  };

  function uniq(vals) {
    return [...new Set(vals.filter(Boolean))].sort();
  }

  function fillSelect(el, values, label) {
    const cur = el.value;
    el.innerHTML = `<option value="">${label}</option>` +
      values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
    el.value = cur && values.includes(cur) ? cur : "";
  }

  function initFilters() {
    const years = uniq(CASES.map((c) => c.year)).sort((a, b) => b - a);
    fillSelect($("#f-year"), years.map(String), "全部年份");
    fillSelect($("#f-type"), uniq(CASES.map((c) => c.manager_type)), "全部类型");
    fillSelect($("#f-region"), uniq(CASES.map((c) => c.region)).sort(
      (a, b) => count(b, "region") - count(a, "region")), "全部地区");
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

  function apply() {
    const q = state.q.trim().toLowerCase();
    view = CASES.filter((c) => {
      if (state.year && String(c.year) !== state.year) return false;
      if (state.type && c.manager_type !== state.type) return false;
      if (state.region && c.region !== state.region) return false;
      if (state.doc && c.doc_type !== state.doc) return false;
      if (state.penalty && !c.penalties.includes(state.penalty)) return false;
      if (state.violation && !c.violation_tags.includes(state.violation)) return false;
      if (q) {
        const hay = (c.title + " " + c.parties.join(" ") + " " + c.org_primary).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    if (state.sort === "date-asc") view.sort((a, b) => a.date.localeCompare(b.date));
    else if (state.sort === "org") view.sort((a, b) => (a.org_primary || "").localeCompare(b.org_primary || "", "zh"));
    else view.sort((a, b) => b.date.localeCompare(a.date));
    page = 1;
    render();
  }

  function render() {
    const pages = Math.max(1, Math.ceil(view.length / PAGE_SIZE));
    if (page > pages) page = pages;
    $("#result-count").textContent = `命中 ${view.length} 例 · 第 ${page}/${pages} 页`;

    const rows = view.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((c) => {
      const tcls = c.manager_type.startsWith("私募证券") ? "type-sec"
        : c.manager_type.startsWith("私募股权") ? "type-eq" : "type-na";
      const name = c.org_primary || c.parties[0] || c.title;
      const sub = c.parties.length > 1 ? c.parties.slice(1).join("、") : "";
      return `<tr>
        <td>${esc(c.date)}</td>
        <td><span class="org" data-id="${c.id}">${esc(name)}</span>
          ${sub ? `<div class="sub2">其他当事人：${esc(sub)}</div>` : ""}
          <div class="sub2">${esc(c.doc_type)}</div></td>
        <td class="${tcls}">${esc(c.manager_type)}</td>
        <td>${esc(c.region || "—")}</td>
        <td>${c.penalties.length ? c.penalties.map((p) => `<span class="tag red">${esc(p)}</span>`).join("") : '<span class="tag grey">—</span>'}</td>
        <td>${c.violation_tags.map((v) => `<span class="tag">${esc(v)}</span>`).join("") || '<span class="tag grey">—</span>'}</td>
        <td><a href="${esc(c.source_url)}" target="_blank" rel="noopener">${c.doc_format === "pdf" ? "PDF" : "网页"} ↗</a></td>
      </tr>`;
    }).join("");
    $("#case-tbody").innerHTML = rows ||
      `<tr><td colspan="7" style="text-align:center;color:#8492a6;padding:26px">没有匹配的案例，试试放宽筛选条件</td></tr>`;

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
    const labels = { year: "年份", type: "类型", region: "地区", doc: "文书", penalty: "措施", violation: "事由", q: "关键词" };
    const items = Object.entries(state).filter(([k, v]) => v && k !== "sort").map(([k, v]) =>
      `<span class="chip">${labels[k]}：${esc(v)} <b data-k="${k}" style="cursor:pointer;color:#b8322c">×</b></span>`);
    $("#active-filters").innerHTML = items.join("") +
      (items.length ? `<span class="chip" id="clear-all" style="cursor:pointer;background:#fdf0ef;border-color:#f6dfdd;color:#b8322c">清空全部 ×</span>` : "");
    document.querySelectorAll("#active-filters b").forEach((b) =>
      b.onclick = () => { state[b.dataset.k] = ""; syncInputs(); apply(); });
    const ca = $("#clear-all");
    if (ca) ca.onclick = () => {
      Object.keys(state).forEach((k) => { if (k !== "sort") state[k] = ""; });
      syncInputs(); apply();
    };
  }

  function syncInputs() {
    $("#q").value = state.q; $("#f-year").value = state.year;
    $("#f-type").value = state.type; $("#f-region").value = state.region;
    $("#f-doc").value = state.doc; $("#f-penalty").value = state.penalty;
    $("#f-violation").value = state.violation;
  }

  function renderStats() {
    const sec = CASES.filter((c) => c.manager_type.startsWith("私募证券")).length;
    const eq = CASES.filter((c) => c.manager_type.startsWith("私募股权")).length;
    const regions = uniq(CASES.map((c) => c.region).filter(Boolean)).length;
    const years = CASES.map((c) => c.year);
    const stats = [
      ["案例总数", CASES.length],
      ["私募证券类", sec],
      ["私募股权创业类", eq],
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

  function bind() {
    $("#q").addEventListener("input", (e) => { state.q = e.target.value; apply(); });
    $("#clear-q").onclick = () => { $("#q").value = ""; state.q = ""; apply(); };
    [["#f-year", "year"], ["#f-type", "type"], ["#f-region", "region"],
     ["#f-doc", "doc"], ["#f-penalty", "penalty"], ["#f-violation", "violation"],
     ["#f-sort", "sort"]].forEach(([sel, key]) =>
      $(sel).addEventListener("change", (e) => { state[key] = e.target.value; apply(); }));

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
    $("#m-meta").innerHTML = [
      `发布日期：${esc(c.date)}`, `文书类型：${esc(c.doc_type)}`,
      `管理人类型：${esc(c.manager_type)}（${esc(c.manager_type_source)}）`,
      `地区：${esc(c.region || "未识别")}`,
      c.penalties.length ? `处分：${esc(c.penalties.join("、"))}` : "",
      c.violation_tags.length ? `事由：${esc(c.violation_tags.join("、"))}` : "",
      `当事人：${esc(c.parties.join("、") || "—")}`
    ].filter(Boolean).map((t) => `<span>${t}</span>`).join("");
    $("#m-link").href = c.source_url;
    $("#m-text").textContent = "正文加载中…";
    $("#modal").hidden = false;

    const show = (t) => {
      $("#m-text").textContent = (t || "").trim() ||
        "（该案例正文为空，请点击查看协会原文）";
    };
    if (TEXTS) return show(TEXTS[String(id)]);
    fetch("data/texts.json").then((r) => r.json()).then((d) => {
      TEXTS = d; show(d[String(id)]);
    }).catch(() => show("正文加载失败，请点击查看协会原文。"));
  }

  fetch("data/cases.json").then((r) => r.json()).then((d) => {
    CASES = d;
    initFilters(); renderStats(); renderCharts(); bind(); apply();
  }).catch((e) => {
    $("#case-tbody").innerHTML =
      `<tr><td colspan="7" style="text-align:center;padding:26px;color:#b8322c">
      数据加载失败（${esc(e.message)}）。本站需通过 HTTP 访问（如 GitHub Pages 或本地静态服务器），
      直接用 file:// 打开会被浏览器安全策略拦截。</td></tr>`;
  });
})();
