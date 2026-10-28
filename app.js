(function(){
  const $ = id => document.getElementById(id);
  const ALL = '全部';
  let cases = [];

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const yearOf = c => (c.date || '').slice(0, 4);
  const money = n => n >= 10000 ? (n / 10000).toLocaleString('zh-CN', {maximumFractionDigits: 2}) + ' 万元' : n.toLocaleString('zh-CN') + ' 元';

  function fillSelect(id, values, desc) {
    const s = $(id);
    s.replaceChildren(new Option(ALL, ''));
    [...new Set(values.filter(Boolean))].sort(desc ? (a, b) => b.localeCompare(a) : undefined)
      .forEach(v => s.append(new Option(v, v)));
  }

  function filtered() {
    const q = $('q').value.trim().toLowerCase();
    const y = $('f-year').value, a = $('f-authority').value,
          m = $('f-measure').value, v = $('f-violation').value;
    let r = cases.filter(c =>
      (!y || yearOf(c) === y) &&
      (!a || c.authority === a) &&
      (!m || c.measure_type === m) &&
      (!v || (c.violation_types || []).includes(v)) &&
      (!q || [c.title, c.respondent, c.document_no, c.summary, c.penalty, c.authority,
              ...(c.legal_basis || []), ...(c.violation_types || []), ...(c.tags || [])]
              .join(' ').toLowerCase().includes(q)));
    const s = $('f-sort').value;
    r.sort((x, y2) =>
      s === 'date-asc' ? x.date.localeCompare(y2.date) :
      s === 'fine-desc' ? (y2.fine_amount || 0) - (x.fine_amount || 0) :
      y2.date.localeCompare(x.date));
    return r;
  }

  function render() {
    const rows = filtered(), list = $('list');
    list.replaceChildren();
    $('empty').hidden = rows.length > 0;
    const total = rows.reduce((t, c) => t + (c.fine_amount || 0), 0);
    $('stats').textContent = `共 ${rows.length} 条案例` + (total ? `，罚没金额合计 ${money(total)}` : '');
    rows.forEach(c => {
      const li = el('li', 'item');
      li.tabIndex = 0;
      li.setAttribute('role', 'button');
      const left = el('div');
      left.append(el('h3', '', c.title),
        el('p', 'sub', `${c.date}　${c.authority}　${c.document_no || ''}`));
      li.append(left);
      const fine = el('div', 'fine');
      if (c.fine_amount) { fine.append(el('b', '', money(c.fine_amount)), el('span', '', '罚款')); }
      li.append(fine, el('p', 'sum', c.summary));
      const tags = el('div', 'tags');
      tags.append(el('span', 'tag m', c.measure_type));
      (c.violation_types || []).forEach(t => tags.append(el('span', 'tag', t)));
      li.append(tags);
      const open = () => { location.hash = c.id; };
      li.addEventListener('click', open);
      li.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      list.append(li);
    });
  }

  function row(dl, label, value, cls) {
    if (!value || (Array.isArray(value) && !value.length)) return;
    dl.append(el('dt', '', label));
    const dd = el('dd', cls || '');
    if (Array.isArray(value)) {
      const ul = el('ul');
      value.forEach(v => ul.append(el('li', '', v)));
      dd.append(ul);
    } else dd.textContent = value;
    dl.append(dd);
  }

  function showDetail() {
    const id = decodeURIComponent(location.hash.slice(1));
    const dlg = $('detail');
    const c = cases.find(x => x.id === id);
    if (!c) { if (dlg.open) dlg.close(); return; }
    $('d-meta').textContent = `${c.date}　${c.authority}　${c.measure_type}`;
    $('d-title').textContent = c.title;
    const dl = $('d-body');
    dl.replaceChildren();
    row(dl, '文号', c.document_no);
    row(dl, '当事人', c.respondent + (c.respondent_type ? `（${c.respondent_type}）` : ''));
    row(dl, '违规类型', c.violation_types);
    row(dl, '处罚结果', c.penalty, 'pen');
    row(dl, '法律依据', c.legal_basis);
    row(dl, '案情摘要', c.summary);
    const src = $('d-src');
    if (c.source_url && /^https?:\/\//.test(c.source_url)) { src.href = c.source_url; src.hidden = false; }
    else src.hidden = true;
    if (!dlg.open) dlg.showModal();
  }

  function init() {
    const years = cases.map(yearOf);
    fillSelect('f-year', years, true);
    fillSelect('f-authority', cases.map(c => c.authority));
    fillSelect('f-measure', cases.map(c => c.measure_type));
    fillSelect('f-violation', cases.flatMap(c => c.violation_types || []));
    $('sample-note').hidden = !cases.some(c => c.sample);
    ['f-year', 'f-authority', 'f-measure', 'f-violation', 'f-sort'].forEach(id => $(id).addEventListener('change', render));
    $('q').addEventListener('input', render);
    $('reset').addEventListener('click', () => {
      $('q').value = '';
      ['f-year', 'f-authority', 'f-measure', 'f-violation'].forEach(id => $(id).value = '');
      $('f-sort').value = 'date-desc';
      render();
    });
    $('d-close').addEventListener('click', () => $('detail').close());
    $('detail').addEventListener('close', () => { if (location.hash) history.replaceState(null, '', location.pathname + location.search); });
    $('detail').addEventListener('click', e => { if (e.target === $('detail')) $('detail').close(); });
    window.addEventListener('hashchange', showDetail);
    render();
    showDetail();
  }

  fetch('data/cases.json')
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(d => { cases = d; init(); })
    .catch(() => {
      $('stats').textContent = '数据加载失败。请通过 http 服务访问（如 python3 -m http.server），不要直接双击打开 html 文件。';
    });
})();
