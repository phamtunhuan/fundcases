const $ = s => document.querySelector(s);
const GROUPS = ['证监会','证监局','中基协','中证协','证券交易所','期货交易所'];
const PAGE = 50;
let D = [], shown = PAGE;
const F = { q:'', g:'', y:'', m:'', r:'', v:'', sort:'date-desc' };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const arr = x => Array.isArray(x) ? x : (x ? [x] : []);
const yen = n => n >= 1e4 ? (n/1e4).toLocaleString('zh-CN',{maximumFractionDigits:2}) + ' 万元' : n + ' 元';

fetch('data/cases.json').then(r => r.json()).then(d => { D = d; init(); })
  .catch(() => { $('#list').innerHTML = '<p class="empty">无法读取 data/cases.json。请通过 GitHub Pages 或本地服务器（python3 -m http.server）打开，不要直接双击 html。</p>'; });

function opts(sel, label, values) {
  $(sel).innerHTML = `<option value="">全部${label}</option>` + values.map(v => `<option>${esc(v)}</option>`).join('');
}
const uniq = f => [...new Set(D.flatMap(c => arr(c[f])))].filter(Boolean);

function init() {
  const gs = GROUPS.filter(g => D.some(c => c.authority_group === g));
  $('#groups').innerHTML = gs.map(g => `<button class="chip" aria-pressed="false" data-g="${g}">${g}</button>`).join('');
  opts('#y', '年份', [...new Set(D.map(c => c.date.slice(0,4)))].sort().reverse());
  opts('#m', '措施', uniq('measure_type'));
  opts('#r', '当事人', uniq('respondent_type'));
  opts('#v', '违规类型', uniq('violation_types'));
  $('#q').oninput = e => { F.q = e.target.value.trim().toLowerCase(); shown = PAGE; render(); };
  for (const k of ['y','m','r','v','sort']) $('#'+k).onchange = e => { F[k] = e.target.value; shown = PAGE; render(); };
  $('#groups').onclick = e => {
    const b = e.target.closest('.chip'); if (!b) return;
    F.g = F.g === b.dataset.g ? '' : b.dataset.g; shown = PAGE; render();
  };
  $('#reset').onclick = () => {
    Object.assign(F, {q:'',g:'',y:'',m:'',r:'',v:'',sort:'date-desc'});
    $('#q').value = ''; for (const k of ['y','m','r','v','sort']) $('#'+k).value = F[k] || (k==='sort' ? 'date-desc' : '');
    shown = PAGE; render();
  };
  $('#more').onclick = () => { shown += PAGE; render(); };
  $('#list').onclick = e => { const b = e.target.closest('.case'); if (b) location.hash = b.dataset.id; };
  $('#dlg').addEventListener('close', () => { if (location.hash) history.replaceState(null, '', location.pathname + location.search); });
  $('#dlg').addEventListener('click', e => { if (e.target === $('#dlg')) $('#dlg').close(); });
  addEventListener('hashchange', openHash);
  render(); openHash();
}

const blob = c => [c.title,c.authority,c.measure_type,c.document_no,c.respondent,c.penalty,c.summary,
  ...arr(c.violation_types),...arr(c.legal_basis),...arr(c.tags)].join(' ').toLowerCase();

function render() {
  document.querySelectorAll('.chip').forEach(b => b.setAttribute('aria-pressed', b.dataset.g === F.g));
  const terms = F.q.split(/\s+/).filter(Boolean);
  let r = D.filter(c =>
    (!F.g || c.authority_group === F.g) && (!F.y || c.date.startsWith(F.y)) &&
    (!F.m || c.measure_type === F.m) && (!F.r || c.respondent_type === F.r) &&
    (!F.v || arr(c.violation_types).includes(F.v)) && terms.every(t => blob(c).includes(t)));
  const [k, dir] = F.sort.split('-');
  r.sort((a, b) => (k === 'date' ? a.date.localeCompare(b.date) : (a.fine_amount||0) - (b.fine_amount||0)) * (dir === 'desc' ? -1 : 1));
  const fine = r.reduce((s, c) => s + (c.fine_amount || 0), 0);
  $('#stat').innerHTML = `共 <b>${r.length}</b> 条案例，罚没金额合计 <b>${fine ? yen(fine) : '—'}</b>`;
  $('#list').innerHTML = r.length ? r.slice(0, shown).map(card).join('') : '<p class="empty">没有符合条件的案例，试试减少筛选条件或换个关键词。</p>';
  $('#more').hidden = r.length <= shown;
}

const card = c => `<button class="case" data-id="${esc(c.id)}">
  <h3 class="title">${esc(c.title)}</h3>
  <div class="meta"><span>${esc(c.date)}</span><span>${esc(c.authority)}</span><span>${esc(c.measure_type)}</span><span>当事人：${esc(c.respondent)}</span></div>
  ${c.penalty ? `<p class="pen">${esc(c.penalty)}</p>` : ''}
  <div class="tags">${arr(c.violation_types).map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div></button>`;

function openHash() {
  const id = decodeURIComponent(location.hash.slice(1)), c = D.find(x => x.id === id);
  if (!c) return;
  const row = (t, v) => v ? `<dt>${t}</dt><dd>${v}</dd>` : '';
  const link = c.source_url && c.source_url !== '#' ? `<a href="${esc(c.source_url)}" target="_blank" rel="noopener noreferrer">查看官方原文</a>` : '';
  $('#detail').innerHTML = `<h2>${esc(c.title)}</h2><dl>
    ${row('日期', esc(c.date))}${row('处罚机关', esc(c.authority))}${row('措施类型', esc(c.measure_type))}
    ${row('文号', esc(c.document_no))}${row('当事人', esc(c.respondent) + (c.respondent_type ? `（${esc(c.respondent_type)}）` : ''))}
    ${row('违规类型', arr(c.violation_types).map(esc).join('、'))}${row('法律依据', arr(c.legal_basis).map(esc).join('<br>'))}
    ${row('处罚结果', esc(c.penalty))}${row('罚没金额', c.fine_amount ? `<span class="fine">${yen(c.fine_amount)}</span>` : '')}
    ${row('案情摘要', esc(c.summary))}
    ${row('标签', arr(c.tags).map(t => `<span class="tag">${esc(t)}</span>`).join(' '))}</dl>
    <div class="actions">${link}<button type="button" onclick="document.getElementById('dlg').close()">关闭</button></div>`;
  if (!$('#dlg').open) $('#dlg').showModal();
}
