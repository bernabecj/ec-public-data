/* bcedata_grid/app_final.js */


const REST_API_BASE = (window.BCEDataGridConfig && window.BCEDataGridConfig.restUrl)
  ? String(window.BCEDataGridConfig.restUrl).replace(/\/?$/, '/')
  : '';
const REST_API_NONCE = (window.BCEDataGridConfig && window.BCEDataGridConfig.nonce)
  ? String(window.BCEDataGridConfig.nonce)
  : '';






const el = (id) => document.getElementById(id);
const perf = {
  enabled: /\bperf=1\b/.test(window.location.search),
  t0: 0,
  firstGrid: false
};

function restApiUrl(path, params = null) {
  if (!REST_API_BASE) throw new Error('REST API base no configurada');
  const cleanPath = String(path || '').replace(/^\/+/, '');
  const url = new URL(cleanPath, REST_API_BASE);
  if (params && typeof params === 'object') {
    Object.entries(params).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') return;
      url.searchParams.set(key, String(value));
    });
  }
  if (perf.enabled) url.searchParams.set('perf', '1');
  return url.toString();
}

function jsonRequestHeaders(withNonce = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (withNonce && REST_API_NONCE) headers['X-WP-Nonce'] = REST_API_NONCE;
  return headers;
}

function ensureDownloadFrame() {
  let frame = document.getElementById('bceDownloadFrame');
  if (frame) return frame;
  frame = document.createElement('iframe');
  frame.id = 'bceDownloadFrame';
  frame.name = 'bceDownloadFrame';
  frame.hidden = true;
  frame.setAttribute('aria-hidden', 'true');
  document.body.appendChild(frame);
  return frame;
}

function submitDownloadRequest(url, payload) {
  const frame = ensureDownloadFrame();
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  form.target = frame.name;
  form.style.display = 'none';
  form.acceptCharset = 'UTF-8';

  const input = document.createElement('input');
  input.type = 'hidden';
  input.name = 'bcedata_payload';
  input.value = JSON.stringify(payload);
  form.appendChild(input);

  document.body.appendChild(form);
  form.submit();
  setTimeout(() => form.remove(), 0);
}

function perfMark(label, data) {
  if (!perf.enabled) return;
  const now = performance.now();
  const delta = perf.t0 ? (now - perf.t0) : 0;
  if (data !== undefined) console.log(`[PERF] ${label} +${delta.toFixed(1)}ms`, data);
  else console.log(`[PERF] ${label} +${delta.toFixed(1)}ms`);
}

// Set textContent only if the element exists (prevents runtime errors if a page variant is loaded).
function setText(id, text) {
  const n = el(id);
  if (n) n.textContent = text;
}

function syncAddToCartButton() {
  const btn = el('btnAddToCart');
  if (!btn) return;
  const hasMarked = !!(state.marked && state.marked.size > 0);
  const message = hasMarked
    ? 'Agregar series seleccionadas a Mi Colección'
    : 'Primero selecciona series para agregarlas a Mi Colección';
  btn.disabled = !hasMarked;
  btn.removeAttribute('title');
  btn.setAttribute('aria-label', message);
  btn.setAttribute('data-bce-tooltip', message);
}

let instantTooltipEl = null;
let instantTooltipTarget = null;
let activeMenuCleanup = null;

function ensureInstantTooltip() {
  if (instantTooltipEl) return instantTooltipEl;
  const node = document.createElement('div');
  node.id = 'bceInstantTooltip';
  node.className = 'bce-instant-tooltip';
  node.setAttribute('role', 'tooltip');
  node.hidden = true;
  document.body.appendChild(node);
  instantTooltipEl = node;
  return node;
}

function isTooltipScope(node) {
  return !!(node && node.closest && node.closest('.bce-appbar, .drawer, .shell, .modal, .popover'));
}

function getInstantTooltipText(node) {
  if (!node) return '';
  const dataTip = node.getAttribute('data-bce-tooltip');
  if (dataTip) return dataTip.trim();
  const title = node.getAttribute('title');
  if (title) {
    const clean = title.trim();
    if (clean) {
      node.setAttribute('data-bce-tooltip', clean);
      node.removeAttribute('title');
      return clean;
    }
  }
  return '';
}

function promoteInstantTooltips(root = document) {
  if (!root || !root.querySelectorAll) return;
  root.querySelectorAll('[title]').forEach((node) => {
    if (!isTooltipScope(node)) return;
    const title = (node.getAttribute('title') || '').trim();
    if (!title) return;
    if (!node.getAttribute('data-bce-tooltip')) node.setAttribute('data-bce-tooltip', title);
    node.removeAttribute('title');
  });
}

function findTooltipTarget(node) {
  if (!node || !node.closest) return null;
  const target = node.closest('[title], [data-bce-tooltip]');
  if (!target || !isTooltipScope(target)) return null;
  return getInstantTooltipText(target) ? target : null;
}

function placeInstantTooltip(clientX, clientY) {
  const tip = ensureInstantTooltip();
  if (tip.hidden) return;
  const gap = 10;
  const maxX = window.innerWidth - tip.offsetWidth - 8;
  const maxY = window.innerHeight - tip.offsetHeight - 8;
  let left = clientX + gap;
  let top = clientY + gap;
  if (left > maxX) left = Math.max(8, clientX - tip.offsetWidth - gap);
  if (top > maxY) top = Math.max(8, clientY - tip.offsetHeight - gap);
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
}

function showInstantTooltip(target, clientX, clientY) {
  const text = getInstantTooltipText(target);
  if (!text) return;
  const tip = ensureInstantTooltip();
  instantTooltipTarget = target;
  tip.textContent = text;
  tip.hidden = false;
  tip.classList.add('is-visible');
  placeInstantTooltip(clientX, clientY);
}

function hideInstantTooltip() {
  if (!instantTooltipEl) return;
  instantTooltipTarget = null;
  instantTooltipEl.hidden = true;
  instantTooltipEl.classList.remove('is-visible');
}

function showInstantTooltipFromFocus(target) {
  const rect = target.getBoundingClientRect();
  showInstantTooltip(target, rect.left + (rect.width / 2), rect.top + (rect.height / 2));
}

function initInstantTooltips() {
  ensureInstantTooltip();

  document.addEventListener('mouseover', (ev) => {
    const target = findTooltipTarget(ev.target);
    if (!target) {
      if (instantTooltipTarget) hideInstantTooltip();
      return;
    }
    if (target !== instantTooltipTarget) showInstantTooltip(target, ev.clientX, ev.clientY);
    else placeInstantTooltip(ev.clientX, ev.clientY);
  });

  document.addEventListener('mousemove', (ev) => {
    if (instantTooltipTarget) placeInstantTooltip(ev.clientX, ev.clientY);
  });

  document.addEventListener('mouseout', (ev) => {
    if (!instantTooltipTarget) return;
    const related = ev.relatedTarget;
    if (related && instantTooltipTarget.contains(related)) return;
    if (ev.target && instantTooltipTarget.contains(ev.target)) hideInstantTooltip();
  });

  document.addEventListener('focusin', (ev) => {
    const target = findTooltipTarget(ev.target);
    if (target) showInstantTooltipFromFocus(target);
  });

  document.addEventListener('focusout', (ev) => {
    if (instantTooltipTarget && ev.target === instantTooltipTarget) hideInstantTooltip();
  });

  document.addEventListener('scroll', () => {
    if (instantTooltipTarget) hideInstantTooltip();
  }, true);
}

const state = {
  treeRaw: [],
  treeBuilt: null,
  activeGrupo: null,
  recent: [],
  bundle: null,

  freq: null,
  unit: null,
  range: { desde: null, hasta: null }, // YYYY-MM
  rangeByFreq: {},
  rangeApplied: false,
  chartRange: { desde: null, hasta: null }, // YYYY-MM (chart)

  grid: { columns: [], rows: [] },

  // Marcados en el grid (candidatos a agregar)
  marked: new Set(), // token strings

  // Colección: items [{token,label,ruta,unidad,frecuencia,graph:false}]
  collection: [],

  chartOn: true,
  chart: null,

  // colores para gráfico (asignación por serie activada para graficar)
  colorMap: new Map(), // key: token|frecuencia -> color
  colorIdx: 0,

  // bloqueo persistente por regla
  lockMsg: null,
  lockMsgAt: 0,

  // cuadros ya seleccionados para cargar rango completo solo la primera vez
  autoInitDone: false,
  collectionSort: 'cuadro',
  collectionRange: { desde: null, hasta: null }, // rango seleccionado para colección (YYYY-MM)
  collectionRangeFull: { desde: null, hasta: null }, // rango completo disponible para colección
};

let seriesChart = null;
let seriesChartCtx = null;
let gridUpdateAllState = null;
let gridEventsBound = false;
let drawerTab = 'cuadro';
let seriesSearchTimer = null;
let lastSeriesQuery = '';
const seriesSearchCache = new Map();
let seriesSearchSeq = 0;
let selectCuadroSeq = 0;
let loadGridSeq = 0;
let pendingFocusToken = null;
let treeFilterTouched = false;
let treeFilterTimer = null;
let lastTreeFilter = '';
const chartRangeCache = new Map();
const chartRangeInFlight = new Map();
const SERIES_SEARCH_LIMIT = 100;
const SEARCH_INPUT_MAX_CHARS = 60;

function hcColors() {
  const opt = (window.Highcharts && Highcharts.getOptions) ? Highcharts.getOptions() : null;
  const colors = opt?.colors;
  return Array.isArray(colors) && colors.length ? colors : ['#2f7ed8','#0d233a','#8bbc21','#910000','#1aadce','#492970','#f28f43','#77a1e5','#c42525','#a6c96a'];
}

function applyHighchartsLang() {
  if (!window.Highcharts || !Highcharts.setOptions) return;
  Highcharts.setOptions({
    lang: {
      contextButtonTitle: 'Menú del gráfico',
      printChart: 'Imprimir gráfico',
      viewFullscreen: 'Pantalla completa',
      exitFullscreen: 'Salir de pantalla completa',
      downloadPNG: 'Descargar PNG',
      downloadJPEG: 'Descargar JPG',
      downloadPDF: 'Descargar PDF',
      downloadSVG: 'Descargar SVG',
      loading: 'Cargando...',
      noData: 'Sin datos'
    }
  });
}

function getExportingOptions() {
  return {
    enabled: true,
    applyStyleSheets: false,
    chartOptions: {
      chart: {
        style: {
          fontFamily: 'Arial, sans-serif'
        }
      }
    },
    buttons: {
      contextButton: {
        align: 'right',
        verticalAlign: 'top',
        x: -8,
        y: 6,
        menuItems: [
          'viewFullscreen',
          'separator',
          'downloadPNG',
          'downloadJPEG',
          'downloadSVG',
          'separator',
          'printChart',
        ]
      }
    }
  };
}

function colorKey(token, frecuencia) {
  return `${token}::${frecuencia}`;
}

function ensureColor(token, frecuencia) {
  const key = colorKey(token, frecuencia);
  if (state.colorMap.has(key)) return state.colorMap.get(key);
  const colors = hcColors();
  const c = colors[state.colorIdx % colors.length];
  state.colorIdx++;
  state.colorMap.set(key, c);
  return c;
}

function setLockMsg(text) {
  state.lockMsg = text || null;
  state.lockMsgAt = state.lockMsg ? Date.now() : 0;
  document.body.classList.toggle('has-inline-msg', !!state.lockMsg);
  if (state.lockMsg) {
    el('inlineText').textContent = state.lockMsg;
    el('inlineMsg').style.display = 'flex';
  } else {
    el('inlineMsg').style.display = 'none';
  }
}

function isGridFullscreen() {
  return document.body.classList.contains('grid-fullscreen');
}

function setGridFullscreen(on) {
  document.body.classList.toggle('grid-fullscreen', !!on);
  const btn = el('btnGridFullscreen');
  if (btn) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.textContent = on ? 'Reducir' : 'Ampliar';
    btn.setAttribute('aria-label', on ? 'Volver a vista normal' : 'Pantalla completa');
    btn.setAttribute('data-bce-tooltip', on ? 'Volver a vista normal' : 'Pantalla completa');
  }
  if (!on) closeDrawer();
  hideMetaPopover();
}
function isPanelSplit() {
  return document.body.classList.contains('panel-split');
}
function setPanelSplit(on) {
  document.body.classList.toggle('panel-split', !!on);
  document.body.classList.toggle('panel-split-fullscreen', !!on);
  const btn = el('btnPanelSplit');
  if (btn) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.textContent = on ? 'Reducir' : 'Ampliar';
    btn.setAttribute('aria-label', on ? 'Volver a vista normal' : 'Pantalla completa');
    btn.setAttribute('data-bce-tooltip', on ? 'Volver a vista normal' : 'Pantalla completa');
  }
  if (on) {
    closeDrawer();
    hideMetaPopover();
  }
  if (state.chart && typeof state.chart.reflow === 'function') {
    setTimeout(() => state.chart.reflow(), 50);
  }
}

async function getJson(url) {
  const t0 = perf.enabled ? performance.now() : 0;
  const r = await fetch(url, { cache:'no-store' });
  const j = await r.json();
  if (perf.enabled) {
    const t1 = performance.now();
    perfMark(`GET ${url}`, `${(t1 - t0).toFixed(1)}ms`);
  }
  if (!r.ok) throw new Error(j?.error || j?.message || 'Error HTTP');
  return j;
}
async function postJson(url, payload, options = {}) {
  const t0 = perf.enabled ? performance.now() : 0;
  const withNonce = options.withNonce !== false;
  const r = await fetch(url, {
    method:'POST',
    headers: jsonRequestHeaders(withNonce),
    body: JSON.stringify(payload)
  });
  // export csv devuelve file, así que solo usar aquí cuando se espere JSON
  const j = await r.json();
  if (perf.enabled) {
    const t1 = performance.now();
    perfMark(`POST ${url}`, `${(t1 - t0).toFixed(1)}ms`);
  }
  if (!r.ok) throw new Error(j?.error || j?.message || 'Error HTTP');
  return j;
}

function fmtNumberEs(v) {
  if (v === null || v === undefined) return '-';
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return n.toLocaleString('es-EC', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function escapeHtml(s) {
  return (s ?? '').toString()
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'",'&#039;');
}

function repairMojibakeText(value) {
  const s = (value ?? '').toString();
  if (!s || !/[ÃÂâ€â€œâ€?â€˜â€™]/.test(s)) return s;
  try {
    const bytes = Uint8Array.from(Array.from(s, ch => ch.charCodeAt(0) & 0xFF));
    const decoded = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    if (decoded && (/[áéíóúñÁÉÍÓÚÑ¿¡]/.test(decoded) || !/[ÃÂâ€â€œâ€?â€˜â€™]/.test(decoded))) {
      return decoded;
    }
  } catch (_) {}
  return s;
}

function wrapLabel(label, maxLen) {
  const text = (label ?? '').toString().trim();
  if (!text) return '';
  if (text.length <= maxLen) return escapeHtml(text);
  let cut = text.lastIndexOf(' ', maxLen);
  if (cut < 0 || cut < Math.floor(maxLen * 0.6)) {
    const next = text.indexOf(' ', maxLen + 1);
    cut = next > -1 ? next : -1;
  }
  if (cut < 0) return escapeHtml(text);
  const a = text.slice(0, cut).trim();
  const b = text.slice(cut + 1).trim();
  return `${escapeHtml(a)}<br>${escapeHtml(b)}`;
}

function indentLabel(label, nivel, opts = {}) {
  const n = Math.max(0, Number(nivel || 0));
  const base = 8;
  const step = 12;
  const pad = n > 0 ? (base + (n - 1) * step) : 0;
  const html = opts.html ? String(label ?? '') : escapeHtml(label);
  return `<span style="padding-left:${pad}px">${html}</span>`;
}

function setTabCount(id, n) {
  const elc = el(id);
  if (!elc) return;
  elc.textContent = `(${Number(n || 0)})`;
}

function setSearchLimitNotice(message) {
  const notice = el('treeFilterNotice');
  if (!notice) return;
  notice.textContent = message || '';
  notice.hidden = !message;
}

function updateSearchInputUi(value) {
  const clearBtn = el('treeFilterClear');
  if (clearBtn) clearBtn.hidden = !String(value || '').length;
}

function normalizeSearchInput(rawValue, inputEl = null) {
  const text = (rawValue || '').toString();
  updateSearchInputUi(text);
  if (text.length < SEARCH_INPUT_MAX_CHARS) {
    setSearchLimitNotice('');
    return text;
  }
  if (text.length === SEARCH_INPUT_MAX_CHARS) {
    setSearchLimitNotice(`Llegó al límite de ${SEARCH_INPUT_MAX_CHARS} caracteres para buscar por cuadro o por serie.`);
    return text;
  }
  const trimmed = text.slice(0, SEARCH_INPUT_MAX_CHARS);
  if (inputEl) inputEl.value = trimmed;
  updateSearchInputUi(trimmed);
  setSearchLimitNotice(`Llegó al límite de ${SEARCH_INPUT_MAX_CHARS} caracteres para buscar por cuadro o por serie. Se recortó el texto ingresado.`);
  return trimmed;
}

function countCuadros(node) {
  if (!node) return 0;
  let c = 0;
  if (node.id_grupo !== null && node.id_grupo !== undefined) c += 1;
  const kids = node.children || [];
  for (const k of kids) c += countCuadros(k);
  return c;
}

function renderSeriesResults(items, query, meta = {}) {
  const host = el('seriesResults');
  if (!host) return;
  const q = (query || '').trim();
  lastSeriesQuery = q;
  if (!q || q.length < 2) {
    host.innerHTML = '<div class="series-empty">Escriba al menos 2 caracteres para buscar series.</div>';
    setTabCount('tabCountSerie', 0);
    return;
  }
  if (!items || !items.length) {
    host.innerHTML = '<div class="series-empty">No se encontraron series.</div>';
    setTabCount('tabCountSerie', 0);
    return;
  }
  const returned = Number(meta.returned ?? items.length) || items.length;
  const htmlItems = items.map(it => {
    const ruta = escapeHtml(it.ruta || '');
    const cuadro = escapeHtml(`${it.cod_grupo || ''} ${it.nom_grupo || ''}`.trim());
    const token = escapeHtml(it.token || '');
    const freq = escapeHtml(it.frecuencia || '');
    const unit = escapeHtml(it.unidad || '');
    const gid = String(it.id_grupo || '');
    const label = escapeHtml(it.nombre_serie || '');
    const alreadyAdded = state.collection.some(col => col.token === (it.token || '') && col.frecuencia === (it.frecuencia || '') && col.unidad === (it.unidad || ''));
    const cartClass = alreadyAdded ? 'series-cart is-added' : 'series-cart';
    const cartTip = alreadyAdded ? 'Serie ya agregada a Mi Colección' : 'Agregar a la colección';
    return `
      <div class="series-item" data-token="${token}" data-freq="${freq}" data-unit="${unit}" data-grupo="${gid}" data-cod="${escapeHtml(it.cod_grupo || '')}" data-nom="${escapeHtml(it.nom_grupo || '')}" data-ruta="${ruta}" data-label="${label}">
        <div class="series-main">
          <div class="series-route">${ruta || '-'}</div>
          <div class="series-cuadro">cuadro: ${cuadro || '-'}</div>
        </div>
        <div class="series-actions">
          <a href="#" data-action="open">[Ir al cuadro]</a>
          <button class="${cartClass}" type="button" data-action="add" data-bce-tooltip="${cartTip}" aria-label="${cartTip}">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path d="M3 5h3l2.2 9.5a2 2 0 0 0 2 1.5h7.5a2 2 0 0 0 2-1.5L22 8H7"></path>
              <circle cx="10" cy="20" r="1.5"></circle>
              <circle cx="18" cy="20" r="1.5"></circle>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join('');
  let html = '';
  if (meta.truncated) {
    html += `<div class="series-empty">Mostrando ${returned} coincidencias más relevantes. Refine la búsqueda si no encuentra la serie.</div>`;
  }
  html += htmlItems;
  host.innerHTML = html;
  promoteInstantTooltips(host);
  setTabCount('tabCountSerie', returned);
}

async function searchSeries(query) {
  const q = (query || '').trim();
  lastSeriesQuery = q;
  if (!q || q.length < 2) {
    renderSeriesResults([], q);
    return;
  }
  if (seriesSearchCache.has(q)) {
    const cached = seriesSearchCache.get(q);
    renderSeriesResults(cached.items || [], q, cached.meta || {});
    return;
  }
  const reqSeq = ++seriesSearchSeq;
  const host = el('seriesResults');
  if (host) host.innerHTML = '<div class="series-empty">Buscando...</div>';
  try {
    const resp = await getJson(restApiUrl('search-series', { q, limit: SERIES_SEARCH_LIMIT }));
    if (reqSeq !== seriesSearchSeq) return;
    const items = resp.items || [];
    const meta = {
      truncated: !!resp.truncated,
      returned: Number(resp.returned ?? items.length) || items.length
    };
    seriesSearchCache.set(q, { items, meta });
    renderSeriesResults(items, q, meta);
  } catch (e) {
    if (reqSeq !== seriesSearchSeq) return;
    renderSeriesResults([], q);
  }
}

function setDrawerTab(tab) {
  drawerTab = (tab === 'serie') ? 'serie' : 'cuadro';
  const tabCuadro = el('tabCuadro');
  const tabSerie = el('tabSerie');
  const paneCuadro = el('tabPaneCuadro');
  const paneSerie = el('tabPaneSerie');
  if (tabCuadro) {
    const on = drawerTab === 'cuadro';
    tabCuadro.classList.toggle('is-active', on);
    tabCuadro.setAttribute('aria-pressed', on ? 'true' : 'false');
  }
  if (tabSerie) {
    const on = drawerTab === 'serie';
    tabSerie.classList.toggle('is-active', on);
    tabSerie.setAttribute('aria-pressed', on ? 'true' : 'false');
  }
  if (paneCuadro) paneCuadro.classList.toggle('is-active', drawerTab === 'cuadro');
  if (paneSerie) paneSerie.classList.toggle('is-active', drawerTab === 'serie');

  const treeFilter = el('treeFilter');
  if (drawerTab === 'cuadro') {
    const q = normalizeSearchInput(treeFilter ? treeFilter.value : '', treeFilter);
    applyTreeFilter(q);
  } else {
    const q = normalizeSearchInput(treeFilter ? treeFilter.value : '', treeFilter);
    searchSeries(q);
  }
}

async function addSeriesFromSearch(item) {
  if (!item) return;
  if (!item.token || !item.frecuencia || !item.unidad) {
    setLockMsg('La serie no tiene frecuencia/unidad disponible para agregar.');
    return;
  }
  const exists = state.collection.some(it => it.token === item.token && it.frecuencia === item.frecuencia && it.unidad === item.unidad);
  if (exists) {
    setLockMsg('La serie ya est\u00e1 en la colecci\u00f3n.');
    return;
  }
  const cuadro = `${item.cod_grupo || ''} ${item.nom_grupo || ''}`.trim();
  let rango = { minYm: null, maxYm: null, freq: item.frecuencia };
  if (Number(item.id_grupo) === Number(state.activeGrupo)) {
    const r = getRangeForFreq(item.frecuencia);
    rango = { minYm: r?.minYm || null, maxYm: r?.maxYm || null, freq: item.frecuencia };
  } else if (item.id_grupo) {
    try {
      const b = await getJson(restApiUrl(`bundle/${item.id_grupo}`));
      const byFreq = b?.range_by_freq?.[item.frecuencia];
      const r = (byFreq && (byFreq.minYm || byFreq.maxYm)) ? byFreq : b?.range;
      rango = { minYm: r?.minYm || null, maxYm: r?.maxYm || null, freq: item.frecuencia };
    } catch (e) {
      // keep null range if bundle not available
    }
  }
  state.collection.push({
    token: item.token,
    label: item.nombre_serie || item.ruta || 'Serie',
    ruta: item.ruta || '',
    cuadro,
    rango,
    unidad: item.unidad,
    frecuencia: item.frecuencia,
    graph: false,
  });
  updateCollectionUI();
  renderGrid();
  if (drawerTab === 'serie' && lastSeriesQuery) {
    const cached = seriesSearchCache.get(lastSeriesQuery);
    renderSeriesResults(cached?.items || [], lastSeriesQuery, cached?.meta || {});
  }
}

function formatYmLabel(ym) {
  if (!ym) return '';
  const m = String(ym).trim().match(/^(\d{4})-(\d{2})$/);
  if (!m) return String(ym);
  const y = m[1];
  const mo = Number(m[2]);
  const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  const mm = months[mo - 1] || m[2];
  return `${y}${mm}`;
}

function formatTooltipDateByFreq(freq, x) {
  if (!window.Highcharts || x === null || x === undefined) return '';
  const f = String(freq || '').toLowerCase();
  if (f === 'anual') return Highcharts.dateFormat('%Y', x);
  if (f === 'mensual') return Highcharts.dateFormat('%Y-%m', x);
  if (f === 'trimestral') {
    const d = new Date(x);
    const y = d.getUTCFullYear();
    const m = d.getUTCMonth() + 1;
    const q = Math.ceil(m / 3);
    const romans = ['I','II','III','IV'];
    return `${y}-${romans[q - 1] || q}`;
  }
  return Highcharts.dateFormat('%Y-%m-%d', x);
}
function formatRangeAvailable(freq, minYm, maxYm) {
  if (!minYm || !maxYm) return '';
  if (freq === 'Anual') {
    const minY = ymToYear(minYm);
    const maxY = ymToYear(maxYm);
    if (!minY || !maxY) return '';
    return `rango disponible: ${minY} - ${maxY}`;
  }
  if (freq === 'Trimestral') {
    const minQ = ymToQuarter(minYm);
    const maxQ = ymToQuarter(maxYm);
    if (!minQ || !maxQ) return '';
    return `rango disponible: ${quarterLabel(minQ.y, minQ.q)} - ${quarterLabel(maxQ.y, maxQ.q)}`;
  }
  return `rango disponible: ${formatYmLabel(minYm)} - ${formatYmLabel(maxYm)}`;
}

function setUnitIndentHalfTitle() {
  const titleRow = el('cuadroTitle')?.parentElement;
  if (!titleRow) return;
  const nameWrap = titleRow.querySelector('.bce-grid-header__namewrap');
  const unitEl = titleRow.querySelector('.bce-grid-header__unit');
  if (!nameWrap || !unitEl) return;
  const codeEl = nameWrap.querySelector('.bce-grid-header__code');
  if (!codeEl) {
    unitEl.style.paddingLeft = '0px';
    return;
  }
  const codeW = codeEl.getBoundingClientRect().width;
  const cs = window.getComputedStyle(codeEl);
  const font = `${cs.fontStyle} ${cs.fontVariant} ${cs.fontWeight} ${cs.fontSize} / ${cs.lineHeight} ${cs.fontFamily}`;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.font = font;
  const spaceW = ctx.measureText(' ').width;
  unitEl.style.paddingLeft = `${Math.round(codeW + spaceW)}px`;
}

let unitIndentResizeTimer = null;
function onUnitIndentResize() {
  if (unitIndentResizeTimer) clearTimeout(unitIndentResizeTimer);
  unitIndentResizeTimer = setTimeout(() => {
    setUnitIndentHalfTitle();
  }, 150);
}

/* ---------------- Drawer ---------------- */

function isDrawerOpen() {
  const drawer = el('drawer');
  return !!drawer && !drawer.classList.contains('drawer-hidden');
}

function openDrawer(initialTab = 'cuadro') {
  el('drawer').classList.remove('drawer-hidden');
  el('drawer').setAttribute('aria-hidden','false');
  el('drawerBackdrop').style.display = 'block';
  const btnDrawer = el('btnDrawer');
  if (btnDrawer) btnDrawer.setAttribute('aria-expanded', 'true');
  const tf = el('treeFilter');
  if (tf) tf.value = '';
  treeFilterTouched = false;
  setTabCount('tabCountCuadro', 0);
  setTabCount('tabCountSerie', 0);
  setDrawerTab(initialTab);
  if (state.treeBuilt) renderTree(state.treeBuilt, false);
}
function closeDrawer() {
  el('drawer').classList.add('drawer-hidden');
  el('drawer').setAttribute('aria-hidden','true');
  el('drawerBackdrop').style.display = 'none';
  const btnDrawer = el('btnDrawer');
  if (btnDrawer) btnDrawer.setAttribute('aria-expanded', 'false');
}
function toggleDrawer(initialTab = 'cuadro') {
  if (isDrawerOpen()) closeDrawer();
  else openDrawer(initialTab);
}

/* ---------------- Tree ---------------- */

function buildTreeFromFlat(nodes) {
  const buildBranch = (items) => {
    const branch = { children: [] };
    if (!Array.isArray(items) || !items.length) return branch;

    const levels = items.map(n => Number(n.num_nivel ?? 0));
    const base = levels.length ? Math.min(...levels) : 0;
    const stack = [branch];

    items.forEach(n => {
      const lvlRaw = Number(n.num_nivel ?? 0);
      const lvl = Math.max(0, lvlRaw - base);
      const hasGrupo = (n.id_grupo !== null && n.id_grupo !== undefined);
      const hasCols = (n.col_inicio !== null && n.col_inicio !== undefined) &&
                      (n.col_fin !== null && n.col_fin !== undefined);
      const kind = hasGrupo
        ? (hasCols ? 'cuadro-group' : 'cuadro')
        : 'group';

      const node = {
        id: n.id_impresion,
        label: n.desc_clasificador ?? '',
        id_grupo: n.id_grupo,
        kind,
        level: lvl,
        children: []
      };

      while (stack.length > lvl + 1) stack.pop();
      stack[stack.length - 1].children.push(node);
      stack.push(node);
    });

    return branch;
  };

  return buildBranch((nodes || []).filter(n => String(n.tipo_clasificador || '') === 'Indices'));
}

function renderTree(root, autoOpen = true) {
  const container = el('tree');
  container.innerHTML = '';
  root.children.forEach(ch => renderTreeNode(container, ch, autoOpen));
}

function ymToIndex(ym) {
  if (!ym || String(ym).length < 7) return null;
  const y = Number(String(ym).slice(0, 4));
  const m = Number(String(ym).slice(5, 7));
  if (!y || !m) return null;
  return y * 12 + (m - 1);
}

function indexToYm(idx) {
  const y = Math.floor(idx / 12);
  const m = (idx % 12) + 1;
  const mm = String(m).padStart(2, '0');
  return `${y}-${mm}`;
}

function shiftYm(ym, deltaMonths) {
  const idx = ymToIndex(ym);
  if (idx === null) return null;
  return indexToYm(idx + deltaMonths);
}

function renderTreeNode(container, node, autoOpen) {
  const isCuadro = node.kind === 'cuadro' || node.kind === 'cuadro-group';
  const isSection = node.kind === 'section';
  const isGroup = node.kind === 'group' || node.kind === 'cuadro-group' || isSection;
  const hasChildren = Array.isArray(node.children) && node.children.length > 0;
  const canToggle = hasChildren && (isGroup || isCuadro);

  const div = document.createElement('div');
  div.className = 'node' + (isCuadro ? ' cuadro' : (isGroup ? ' group' : ''));
  if (isSection) div.classList.add('section');
  const lvlNum = Number(node.level);
  if (isSection) {
    div.classList.add('level-section');
  } else if (Number.isFinite(lvlNum)) {
    let lvlClass = 'level-3';
    if (lvlNum <= 0) lvlClass = 'level-1';
    else if (lvlNum === 1) lvlClass = 'level-2';
    else if (lvlNum === 2) lvlClass = 'level-3';
    else lvlClass = 'level-4';
    div.classList.add(lvlClass);
  }

  const twisty = document.createElement('div');
  twisty.className = 'twisty';
  twisty.textContent = canToggle ? '+' : '';

  const label = document.createElement('div');
  label.className = 'label';
  label.textContent = node.label;
  label.style.cursor = isCuadro ? 'pointer' : 'default';

  div.appendChild(twisty);
  div.appendChild(label);

  if (isCuadro && state.activeGrupo === Number(node.id_grupo)) div.classList.add('active');
  if (isCuadro && state.recent.includes(Number(node.id_grupo))) div.classList.add('recent');

  const childrenWrap = document.createElement('div');
  childrenWrap.style.paddingLeft = '14px';

  // Mostrar niveles hasta 4 por defecto (expandir hasta nivel 2).
  childrenWrap.style.display = 'none';
  if (canToggle) {
    const hasCuadroChild = node.children && node.children.some(ch => ch.kind === 'cuadro' || ch.kind === 'cuadro-group');
    const shouldOpen = autoOpen && (isSection || (lvlNum <= 2) || (lvlNum === 3 && hasCuadroChild));
    if (shouldOpen) {
      childrenWrap.style.display = 'block';
      twisty.textContent = '-';
      div.classList.add('open');
    } else {
      twisty.textContent = '+';
    }
  }

  if (canToggle) {
    twisty.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const open = childrenWrap.style.display !== 'none';
      childrenWrap.style.display = open ? 'none' : 'block';
      twisty.textContent = open ? '+' : '-';
      div.classList.toggle('open', !open);
    });
  }

  if (hasChildren) {
    node.children.forEach(ch => renderTreeNode(childrenWrap, ch, autoOpen));
  }

  if (isCuadro) {
    label.addEventListener('click', (ev) => {
      ev.stopPropagation();
      selectCuadro(Number(node.id_grupo));
    });
  }

  // La expansion solo ocurre con el signo +/-.
  container.appendChild(div);
  container.appendChild(childrenWrap);
}

function applyTreeFilter(q) {
  q = (q ?? '').trim().toLowerCase();
  if (q === lastTreeFilter) return;
  lastTreeFilter = q;
  if (!q) {
    renderTree(state.treeBuilt, false);
    if (treeFilterTouched) setTabCount('tabCountCuadro', countCuadros(state.treeBuilt));
    return;
  }

  const filterNode = (node) => {
    const hit = (node.label ?? '').toLowerCase().includes(q);
    const kids = node.children.map(filterNode).filter(Boolean);
    if (hit || kids.length) return { ...node, children: kids };
    return null;
  };
  const filtered = { children: state.treeBuilt.children.map(filterNode).filter(Boolean) };
  if (!filtered.children.length) {
    const treeEl = el('tree');
    if (treeEl) {
      treeEl.innerHTML = '<div class="series-empty">Sin resultados en Índice. Pruebe en “Por Serie”.</div>';
    }
    setTabCount('tabCountCuadro', 0);
    return;
  }
  renderTree(filtered);
  setTabCount('tabCountCuadro', countCuadros(filtered));
}

/* ---------------- Cuadro / Bundle ---------------- */

async function selectCuadro(id_grupo) {
  const reqSeq = ++selectCuadroSeq;
  loadGridSeq++;
  hideMetaPopover();
  if (perf.enabled) perfMark(`selectCuadro ${id_grupo} start`);
  state.activeGrupo = id_grupo;
  state.rangeByFreq = {};
  state.recent = [id_grupo, ...state.recent.filter(x=>x!==id_grupo)].slice(0,5);
  const treeFilter = el('treeFilter');
  if (treeFilter) treeFilter.value = '';

  // reset selección operativa del cuadro
  state.marked = new Set();
  // Mantener colección y gráfico al cambiar de cuadro (wireframe).
setLockMsg(null);

  // UI while loading
  el('selFreq').disabled = true;
  el('selUnit').disabled = true;
  el('btnCuadro').disabled = true;
  syncAddToCartButton();

  el('gridEmpty').textContent = 'Cargando cuadro...';
  el('gridEmpty').style.display = 'flex';
  el('gridScroll').style.display = 'none';

  renderTree(state.treeBuilt);
  closeDrawer();

  if (id_grupo === 200) {
    setText('cuadroTitle', 'Cuadro no disponible');
    const cuadroSub = el('cuadroSub');
    if (cuadroSub) cuadroSub.innerHTML = '';
    setLockMsg('Este cuadro aún no existe en la BD.');
    return;
  }

  try {
    const b = await getJson(restApiUrl(`bundle/${id_grupo}`));
    if (reqSeq !== selectCuadroSeq || state.activeGrupo !== id_grupo) return;
    state.bundle = b;
    if (perf.enabled) perfMark(`bundle loaded ${id_grupo}`);

    const nameRaw = b.context.nom_alias_grupo ? String(b.context.nom_alias_grupo) : (b.context.nom_grupo ? String(b.context.nom_grupo) : '');
    let nameMain = nameRaw;
    let nameParen = '';
    const m = nameRaw.match(/^(.*?)(\s*\([^)]*\))\s*$/);
    if (m) {
      nameMain = m[1] || '';
      nameParen = (m[2] || '').trim();
    }
    const titleParts = [];
    const nameTrim = nameMain.trim();
    const codeMatch = nameTrim.match(/^(\d+(?:\.\d+)+)\s+(.*)$/);
    if (codeMatch) {
      const code = codeMatch[1];
      const text = codeMatch[2] || '';
      titleParts.push(`<span class="bce-grid-header__code">${escapeHtml(code)}</span>`);
      titleParts.push(`<span class="bce-grid-header__name">${escapeHtml(text)}</span>`);
    } else if (nameTrim) {
      titleParts.push(`<span class="bce-grid-header__name">${escapeHtml(nameTrim)}</span>`);
    }
    if (nameParen) titleParts.push(`<span class="bce-grid-header__paren">${escapeHtml(nameParen)}</span>`);
    const titleEl = el('cuadroTitle');
    if (titleEl) titleEl.innerHTML = `<div class="bce-grid-header__namewrap">${titleParts.join(' ')}</div>`;
    const minYm = b.range?.minYm || '';
    const maxYm = b.range?.maxYm || '';
    const unitGroup = (b.context?.unidad_grupo || '').toString().trim();
    const unitText = unitGroup ? escapeHtml(unitGroup) : '';
    const unitLine = unitText ? `${unitText}.` : '';
    const titleRow = titleEl ? titleEl.parentElement : null;
    const prevUnit = titleRow?.querySelector('.bce-grid-header__unit');
    if (prevUnit) prevUnit.remove();
    if (unitLine && titleRow) {
      const stack = titleRow.querySelector('.bce-grid-header__stack');
      const stackHtml = `
        <div class="bce-grid-header__stack">
          <div class="bce-grid-header__namewrap">${titleParts.join(' ')}</div>
          <div class="bce-grid-header__unit"><span class="unit-name">${unitText}</span>.</div>
        </div>
      `;
      if (stack) {
        stack.outerHTML = stackHtml;
      } else {
        const nameWrap = titleRow.querySelector('.bce-grid-header__namewrap');
        if (nameWrap) nameWrap.outerHTML = stackHtml;
        else titleRow.insertAdjacentHTML('afterbegin', stackHtml);
      }
      requestAnimationFrame(() => setUnitIndentHalfTitle());
    }
    // Frecuencia selector: mostrar todas las disponibles
    const selFreq = el('selFreq');
    selFreq.innerHTML = '';
    (b.frecuencias || []).forEach(f => {
      const opt = document.createElement('option');
      opt.value = f; opt.textContent = f;
      selFreq.appendChild(opt);
    });

    // Frecuencia inicial: prioriza Mensual; si no existe, Anual; si no, la primera disponible.
    state.freq = pickInitialFreqForCuadro(b.frecuencias || [], b.default_frequency || null);
    selFreq.value = state.freq || '';
    selFreq.disabled = false;
    setText('freqVal', state.freq || '');
    // rango por defecto: siempre todo el rango disponible
    const r2 = getRangeForCurrentFreq();
    const maxYm2 = r2.maxYm;
    const minYm2 = r2.minYm;
    let desde = minYm2, hasta = maxYm2;
    if (maxYm2) hasta = maxYm2;
    state.range.desde = desde;
    state.range.hasta = hasta;
    state.rangeApplied = false;
    el('inpDesde').value = desde || '';
    el('inpHasta').value = hasta || '';
    applyCalendarMode();
    updatePeriodoVal();

    // Unidad selector: autoselecciona primera unidad de la frecuencia inicial
    await applyUnitPolicyAndLoad(true);
    if (reqSeq !== selectCuadroSeq || state.activeGrupo !== id_grupo) return;

    // botones
    el('btnCuadro').disabled = false;

  } catch (e) {
    setLockMsg(`Error: ${e.message}`);
    el('gridEmpty').textContent = 'Error al cargar.';
  }
}

function getUnitsForFreq(freq) {
  return state.bundle?.unidades?.[freq] || [];
}

function getAllUnits() {
  const out = [];
  const seen = new Set();
  ['Semanal','Mensual','Trimestral','Anual'].forEach((f) => {
    const units = state.bundle?.unidades?.[f] || [];
    units.forEach((u) => {
      if (seen.has(u)) return;
      seen.add(u);
      out.push(u);
    });
  });
  return out;
}

function isValidUnitForFreq(unit, freq) {
  if (!unit || !freq) return false;
  return getUnitsForFreq(freq).includes(unit);
}

function getUnitsForCurrentFreq() {
  return getUnitsForFreq(state.freq);
}

function pickInitialFreqForCuadro(frecuencias, defaultFrequency = null) {
  const available = Array.isArray(frecuencias) ? frecuencias.filter(Boolean) : [];
  if (!available.length) return defaultFrequency || null;
  if (available.includes('Mensual')) return 'Mensual';
  if (available.includes('Anual')) return 'Anual';
  if (defaultFrequency && available.includes(defaultFrequency)) return defaultFrequency;
  return available[0] || null;
}

function getRangeForFreq(freq) {
  const byFreq = state.bundle?.range_by_freq?.[freq];
  if (byFreq && (byFreq.minYm || byFreq.maxYm)) return byFreq;
  return state.bundle?.range || { minYm: null, maxYm: null };
}

function getRangeForCurrentFreq() {
  return getRangeForFreq(state.freq);
}

function ymToYear(ym) {
  return ym ? Number(String(ym).slice(0, 4)) : null;
}

function ymToQuarter(ym) {
  if (!ym || String(ym).length < 7) return null;
  const y = Number(String(ym).slice(0, 4));
  const m = Number(String(ym).slice(5, 7));
  if (!y || !m) return null;
  const q = Math.ceil(m / 3);
  return { y, q };
}

function quarterLabel(y, q) {
  const roman = ['I','II','III','IV'][q - 1] || 'I';
  return `${y} - ${roman}`;
}

function isYm(val) {
  return /^\d{4}-\d{2}$/.test(String(val || ''));
}

function parseYearInput(val) {
  const v = String(val || '').trim();
  const m = v.match(/^(\d{4})(?:-(\d{2}))?$/);
  if (!m) return null;
  return Number(m[1]);
}

function nextYm(ym) {
  if (!isYm(ym)) return null;
  const y = Number(ym.slice(0, 4));
  const m = Number(ym.slice(5, 7));
  if (!y || !m) return null;
  const nm = m === 12 ? 1 : (m + 1);
  const ny = m === 12 ? (y + 1) : y;
  return `${ny}-${String(nm).padStart(2, '0')}`;
}

function fillRangeSelects(freq, minYm, maxYm, selDesde, selHasta) {
  const inpDesde = el('inpDesde');
  const inpHasta = el('inpHasta');
  if (!inpDesde || !inpHasta) return;
  inpDesde.innerHTML = '';
  inpHasta.innerHTML = '';

  const addOpt = (select, value, text, isSelected) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = text;
    if (isSelected) opt.selected = true;
    select.appendChild(opt);
  };

  if (!minYm || !maxYm) return;

  if (freq === 'Anual') {
    const minY = ymToYear(minYm);
    const maxY = ymToYear(maxYm);
    if (!minY || !maxY) return;
    for (let y = minY; y <= maxY; y++) {
      addOpt(inpDesde, String(y), String(y), String(y) === String(selDesde));
      addOpt(inpHasta, String(y), String(y), String(y) === String(selHasta));
    }
    return;
  }

  if (freq === 'Trimestral') {
    const minQ = ymToQuarter(minYm);
    const maxQ = ymToQuarter(maxYm);
    if (!minQ || !maxQ) return;
    const minKey = quarterKey(minQ.y, minQ.q);
    const maxKey = quarterKey(maxQ.y, maxQ.q);
    for (let key = minKey; key <= maxKey; key++) {
      const yy = Math.floor((key - 1) / 4);
      const qq = key - (yy * 4);
      const label = quarterLabel(yy, qq);
      addOpt(inpDesde, label, label, label === selDesde);
      addOpt(inpHasta, label, label, label === selHasta);
    }
    return;
  }

  let cur = minYm;
  while (cur && cur <= maxYm) {
    addOpt(inpDesde, cur, cur, cur === selDesde);
    addOpt(inpHasta, cur, cur, cur === selHasta);
    const nxt = nextYm(cur);
    if (!nxt) break;
    cur = nxt;
  }
}

function quarterToRange(y, q) {
  const startMonth = (q - 1) * 3 + 1;
  const endMonth = startMonth + 2;
  return {
    startYm: `${y}-${String(startMonth).padStart(2, '0')}`,
    endYm: `${y}-${String(endMonth).padStart(2, '0')}`
  };
}

function quarterKey(y, q) {
  return y * 4 + q;
}

function clampYear(y, minY, maxY) {
  if (minY && y < minY) return minY;
  if (maxY && y > maxY) return maxY;
  return y;
}

function clampQuarter(y, q, minQ, maxQ) {
  let key = quarterKey(y, q);
  if (minQ !== null && key < minQ) key = minQ;
  if (maxQ !== null && key > maxQ) key = maxQ;
  const yy = Math.floor((key - 1) / 4);
  const qq = key - (yy * 4);
  return { y: yy, q: qq };
}

function applyCalendarMode() {
  const inpDesde = el('inpDesde');
  const inpHasta = el('inpHasta');
  if (!inpDesde || !inpHasta) return;

  const range = getRangeForCurrentFreq();
  const minYm = range.minYm || '';
  const maxYm = range.maxYm || '';

  if (state.freq === 'Anual') {
    const y1 = ymToYear(state.range.desde) || ymToYear(minYm);
    const y2 = ymToYear(state.range.hasta) || ymToYear(maxYm);
    fillRangeSelects(state.freq, minYm, maxYm, y1, y2);
    return;
  }

  if (state.freq === 'Trimestral') {
    const dQ = ymToQuarter(state.range.desde) || ymToQuarter(minYm);
    const hQ = ymToQuarter(state.range.hasta) || ymToQuarter(maxYm);
    const dLabel = dQ ? quarterLabel(dQ.y, dQ.q) : '';
    const hLabel = hQ ? quarterLabel(hQ.y, hQ.q) : '';
    fillRangeSelects(state.freq, minYm, maxYm, dLabel, hLabel);
    return;
  }

  fillRangeSelects(state.freq, minYm, maxYm, state.range.desde || minYm, state.range.hasta || maxYm);
}

function fillYearSelects(minYm, maxYm, selDesde, selHasta, fromEl, toEl) {
  if (!fromEl || !toEl || !minYm || !maxYm) return;
  const minY = ymToYear(minYm);
  const maxY = ymToYear(maxYm);
  if (!minY || !maxY) return;
  fromEl.innerHTML = '';
  toEl.innerHTML = '';
  for (let y = minY; y <= maxY; y++) {
    const opt1 = document.createElement('option');
    opt1.value = String(y);
    opt1.textContent = String(y);
    if (String(y) === String(selDesde)) opt1.selected = true;
    fromEl.appendChild(opt1);

    const opt2 = document.createElement('option');
    opt2.value = String(y);
    opt2.textContent = String(y);
    if (String(y) === String(selHasta)) opt2.selected = true;
    toEl.appendChild(opt2);
  }
}

function updateCollectionRangeInputs() {
  const fromEl = el('collDesde');
  const toEl = el('collHasta');
  const btn = el('btnCollRange');
  if (!fromEl || !toEl || !btn) return;

  const full = state.collectionRangeFull;
  const hasRange = !!(full?.desde && full?.hasta && state.collection.length);
  btn.disabled = !hasRange;
  if (!hasRange) {
    fromEl.innerHTML = '';
    toEl.innerHTML = '';
    return;
  }

  const selDesde = state.collectionRange?.desde || full.desde;
  const selHasta = state.collectionRange?.hasta || full.hasta;
  const selDesdeY = ymToYear(selDesde) || ymToYear(full.desde);
  const selHastaY = ymToYear(selHasta) || ymToYear(full.hasta);
  fillYearSelects(full.desde, full.hasta, selDesdeY, selHastaY, fromEl, toEl);
  fromEl.value = String(selDesdeY);
  toEl.value = String(selHastaY);
}

function setCollectionRangeFull(range, forceReset) {
  if (!range?.desde || !range?.hasta) {
    state.collectionRangeFull = { desde: null, hasta: null };
    state.collectionRange = { desde: null, hasta: null };
    updateCollectionRangeInputs();
    return;
  }

  const full = { desde: range.desde, hasta: range.hasta };
  state.collectionRangeFull = full;

  let sel = state.collectionRange?.desde && state.collectionRange?.hasta
    ? { ...state.collectionRange }
    : null;
  if (!sel || forceReset) {
    sel = { ...full };
  } else {
    if (sel.desde < full.desde) sel.desde = full.desde;
    if (sel.hasta > full.hasta) sel.hasta = full.hasta;
    if (sel.desde > sel.hasta) sel = { ...full };
  }

  state.collectionRange = sel;
  updateCollectionRangeInputs();
}

function readCollectionRangeFromInputs() {
  const fromEl = el('collDesde');
  const toEl = el('collHasta');
  const full = state.collectionRangeFull;
  if (!fromEl || !toEl || !full?.desde || !full?.hasta) return null;
  const minY = ymToYear(full.desde);
  const maxY = ymToYear(full.hasta);
  let y1 = Number(fromEl.value || minY);
  let y2 = Number(toEl.value || maxY);
  if (!y1 || !y2) return null;
  y1 = clampYear(y1, minY, maxY);
  y2 = clampYear(y2, minY, maxY);
  if (y1 > y2) return null;
  return { desde: `${y1}-01`, hasta: `${y2}-12` };
}

function applyCollectionRange(range) {
  if (!range?.desde || !range?.hasta) return;
  state.collectionRange = { desde: range.desde, hasta: range.hasta };
  state.chartRange = { desde: range.desde, hasta: range.hasta };
  updateCollectionRangeInputs();
  refreshChart();
}

async function applyQuickChartRange(monthsBack) {
  const active = activeGraphItems();
  if (!active.length) {
    setLockMsg('No hay series activas para graficar.');
    return;
  }
  const full = await fetchFullGraphRange(active);
  if (!full?.desde || !full?.hasta) {
    setLockMsg('No hay rango disponible para las series activas.');
    return;
  }
  const maxYm = full.hasta;
  const minYm = full.desde;
  const start = shiftYm(maxYm, -(monthsBack - 1));
  const desde = (start && start < minYm) ? minYm : start;
  const hasta = maxYm;
  if (!desde || !hasta) return;
  state.chartRange = { desde, hasta };
  refreshChart();
}

function applySeriesCalendarMode(freq, desde, hasta) {
  const ensureChartRangeControl = (id, tagName) => {
    const current = el(id);
    if (!current) return null;
    if (current.tagName.toLowerCase() === tagName) return current;
    const next = document.createElement(tagName);
    next.id = current.id;
    next.className = current.className;
    current.replaceWith(next);
    return next;
  };
  const addOpt = (select, value, text, isSelected) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = text;
    if (isSelected) opt.selected = true;
    select.appendChild(opt);
  };
  let inpDesde = el('chartDesde');
  let inpHasta = el('chartHasta');
  if (!inpDesde || !inpHasta) return;

  const range = getRangeForFreq(freq);
  const minYm = range.minYm || '';
  const maxYm = range.maxYm || '';

  if (freq === 'Anual') {
    inpDesde = ensureChartRangeControl('chartDesde', 'select');
    inpHasta = ensureChartRangeControl('chartHasta', 'select');
    if (!inpDesde || !inpHasta) return;
    const minY = ymToYear(minYm);
    const maxY = ymToYear(maxYm);
    const y1 = desde ? ymToYear(desde) : null;
    const y2 = hasta ? ymToYear(hasta) : null;
    inpDesde.innerHTML = '';
    inpHasta.innerHTML = '';
    if (!minY || !maxY) return;
    for (let y = minY; y <= maxY; y++) {
      addOpt(inpDesde, String(y), String(y), String(y) === String(y1 || minY));
      addOpt(inpHasta, String(y), String(y), String(y) === String(y2 || maxY));
    }
    return;
  }

  if (freq === 'Trimestral') {
    inpDesde = ensureChartRangeControl('chartDesde', 'select');
    inpHasta = ensureChartRangeControl('chartHasta', 'select');
    if (!inpDesde || !inpHasta) return;
    const minQ = ymToQuarter(minYm);
    const maxQ = ymToQuarter(maxYm);
    const dQ = ymToQuarter(desde) || minQ;
    const hQ = ymToQuarter(hasta) || maxQ;
    if (!minQ || !maxQ) return;
    const minKey = quarterKey(minQ.y, minQ.q);
    const maxKey = quarterKey(maxQ.y, maxQ.q);
    const dLabel = dQ ? quarterLabel(dQ.y, dQ.q) : '';
    const hLabel = hQ ? quarterLabel(hQ.y, hQ.q) : '';
    inpDesde.innerHTML = '';
    inpHasta.innerHTML = '';
    for (let key = minKey; key <= maxKey; key++) {
      const yy = Math.floor((key - 1) / 4);
      const qq = key - (yy * 4);
      const label = quarterLabel(yy, qq);
      addOpt(inpDesde, label, label, label === dLabel);
      addOpt(inpHasta, label, label, label === hLabel);
    }
    return;
  }

  inpDesde = ensureChartRangeControl('chartDesde', 'select');
  inpHasta = ensureChartRangeControl('chartHasta', 'select');
  if (!inpDesde || !inpHasta) return;
  inpDesde.innerHTML = '';
  inpHasta.innerHTML = '';
  if (!minYm || !maxYm) return;

  let cur = minYm;
  const selDesde = desde || minYm;
  const selHasta = hasta || maxYm;
  while (cur && cur <= maxYm) {
    addOpt(inpDesde, cur, cur, cur === selDesde);
    addOpt(inpHasta, cur, cur, cur === selHasta);
    const nxt = nextYm(cur);
    if (!nxt) break;
    cur = nxt;
  }
}

function parseQuarterInput(val) {
  const v = String(val || '').trim().toUpperCase();
  const m = v.match(/^(\d{4})\s*(?:[-\u2013]\s*)?(I|II|III|IV)$/);
  if (!m) return null;
  const map = { I:1, II:2, III:3, IV:4 };
  return { y: Number(m[1]), q: map[m[2]] || 1 };
}

function readRangeFromInputs() {
  const inpDesde = el('inpDesde');
  const inpHasta = el('inpHasta');
  const range = getRangeForCurrentFreq();
  const minYm = range.minYm || '';
  const maxYm = range.maxYm || '';

  if (state.freq === 'Anual') {
    const minY = ymToYear(minYm);
    const maxY = ymToYear(maxYm);
    let y1 = parseYearInput(inpDesde.value);
    let y2 = parseYearInput(inpHasta.value);
    if (!y1 && minY) y1 = minY;
    if (!y2 && maxY) y2 = maxY;
    if (!y1 || !y2) return null;
    y1 = clampYear(y1, minY, maxY);
    y2 = clampYear(y2, minY, maxY);
    if (y1 > y2) return null;
    inpDesde.value = String(y1);
    inpHasta.value = String(y2);
    return { desde: `${y1}-01`, hasta: `${y2}-12` };
  }

  if (state.freq === 'Trimestral') {
    const minQ = ymToQuarter(minYm);
    const maxQ = ymToQuarter(maxYm);
    const minKey = minQ ? quarterKey(minQ.y, minQ.q) : null;
    const maxKey = maxQ ? quarterKey(maxQ.y, maxQ.q) : null;
    let d = parseQuarterInput(inpDesde.value);
    let h = parseQuarterInput(inpHasta.value);
    if (!d && minQ) d = { y: minQ.y, q: minQ.q };
    if (!h && maxQ) h = { y: maxQ.y, q: maxQ.q };
    if (!d || !h) return null;
    d = clampQuarter(d.y, d.q, minKey, maxKey);
    h = clampQuarter(h.y, h.q, minKey, maxKey);
    if (quarterKey(d.y, d.q) > quarterKey(h.y, h.q)) return null;
    const dRange = quarterToRange(d.y, d.q);
    const hRange = quarterToRange(h.y, h.q);
    inpDesde.value = quarterLabel(d.y, d.q);
    inpHasta.value = quarterLabel(h.y, h.q);
    return { desde: dRange.startYm, hasta: hRange.endYm };
  }

  const d = inpDesde.value;
  const h = inpHasta.value;
  if (!d || !h) return null;
  if (minYm && d < minYm) inpDesde.value = minYm;
  if (maxYm && h > maxYm) inpHasta.value = maxYm;
  return { desde: inpDesde.value, hasta: inpHasta.value };
}

function readSeriesRangeFromInputs(freq) {
  return getSeriesRangeInputState(freq).parsed;
}

function getSeriesRangeInputState(freq) {
  const inpDesde = el('chartDesde');
  const inpHasta = el('chartHasta');
  if (!inpDesde || !inpHasta) return { parsed: null, error: 'empty' };

  const range = getRangeForFreq(freq);
  const minYm = range.minYm || '';
  const maxYm = range.maxYm || '';

  if (freq === 'Anual') {
    const minY = ymToYear(minYm);
    const maxY = ymToYear(maxYm);
    let y1 = parseYearInput(inpDesde.value);
    let y2 = parseYearInput(inpHasta.value);
    if (!y1 && minY) y1 = minY;
    if (!y2 && maxY) y2 = maxY;
    if (!y1 || !y2) return { parsed: null, error: 'empty' };
    y1 = clampYear(y1, minY, maxY);
    y2 = clampYear(y2, minY, maxY);
    if (y1 > y2) return { parsed: null, error: 'order' };
    inpDesde.value = String(y1);
    inpHasta.value = String(y2);
    return { parsed: { desde: `${y1}-01`, hasta: `${y2}-12` }, error: null };
  }

  if (freq === 'Trimestral') {
    const minQ = ymToQuarter(minYm);
    const maxQ = ymToQuarter(maxYm);
    const minKey = minQ ? quarterKey(minQ.y, minQ.q) : null;
    const maxKey = maxQ ? quarterKey(maxQ.y, maxQ.q) : null;
    const d0 = parseQuarterInput(inpDesde.value) || ymToQuarter(minYm);
    const h0 = parseQuarterInput(inpHasta.value) || ymToQuarter(maxYm);
    if (!d0 || !h0) return { parsed: null, error: 'empty' };
    let d = clampQuarter(d0.y, d0.q, minKey, maxKey);
    let h = clampQuarter(h0.y, h0.q, minKey, maxKey);
    if (quarterKey(d.y, d.q) > quarterKey(h.y, h.q)) return { parsed: null, error: 'order' };
    const dRange = quarterToRange(d.y, d.q);
    const hRange = quarterToRange(h.y, h.q);
    inpDesde.value = quarterLabel(d.y, d.q);
    inpHasta.value = quarterLabel(h.y, h.q);
    return { parsed: { desde: dRange.startYm, hasta: hRange.endYm }, error: null };
  }

  const d = inpDesde.value;
  const h = inpHasta.value;
  if (!isYm(d) || !isYm(h)) return { parsed: null, error: 'empty' };
  if (d > h) return { parsed: null, error: 'order' };
  if (minYm && d < minYm) inpDesde.value = minYm;
  if (maxYm && h > maxYm) inpHasta.value = maxYm;
  if (inpDesde.value > inpHasta.value) return { parsed: null, error: 'order' };
  return { parsed: { desde: inpDesde.value, hasta: inpHasta.value }, error: null };
}

function updatePeriodoVal() {
  const r = getRangeForCurrentFreq();
  const minYm = r.minYm || '';
  const maxYm = r.maxYm || '';
  if (state.freq === 'Anual') {
    const minY = ymToYear(minYm);
    const maxY = ymToYear(maxYm);
    const value = (minY && maxY) ? `${minY} a ${maxY}` : '';
    setText('periodoVal', value);
    setText('periodoControlVal', value);
    return;
  }
  if (state.freq === 'Trimestral') {
    const minQ = ymToQuarter(minYm);
    const maxQ = ymToQuarter(maxYm);
    const a = minQ ? quarterLabel(minQ.y, minQ.q) : '';
    const b = maxQ ? quarterLabel(maxQ.y, maxQ.q) : '';
    const value = (a && b) ? `${a} a ${b}` : '';
    setText('periodoVal', value);
    setText('periodoControlVal', value);
    return;
  }
  const value = (minYm && maxYm) ? `${minYm} a ${maxYm}` : '';
  setText('periodoVal', value);
  setText('periodoControlVal', value);
}

function normalizeRangeForFreq() {
  const r = getRangeForCurrentFreq();
  const minYm = r.minYm || null;
  const maxYm = r.maxYm || null;
  if (!minYm || !maxYm) return;
  if (!state.range.desde || state.range.desde < minYm) state.range.desde = minYm;
  if (!state.range.hasta || state.range.hasta > maxYm) state.range.hasta = maxYm;
  if (state.range.desde > state.range.hasta) {
    state.range.desde = minYm;
    state.range.hasta = maxYm;
  }
}

function adaptRangeByYears(prevDesde, prevHasta) {
  const r = getRangeForCurrentFreq();
  const minYm = r.minYm || null;
  const maxYm = r.maxYm || null;
  if (!minYm || !maxYm) return false;

  const minY = ymToYear(minYm);
  const maxY = ymToYear(maxYm);
  if (!minY || !maxY) return false;

  const yFrom = ymToYear(prevDesde) || minY;
  const yTo = ymToYear(prevHasta) || maxY;
  let yf = clampYear(yFrom, minY, maxY);
  let yt = clampYear(yTo, minY, maxY);
  if (yf > yt) { yf = minY; yt = maxY; }

  let desdeUse = `${yf}-01`;
  let hastaUse = `${yt}-12`;
  if (minYm && desdeUse < minYm) desdeUse = minYm;
  if (maxYm && hastaUse > maxYm) hastaUse = maxYm;

  state.range.desde = desdeUse;
  state.range.hasta = hastaUse;
  return true;
}
async function applyUnitPolicyAndLoad(forceFirstUnit) {
  const selUnit = el('selUnit');
  selUnit.innerHTML = '';
  selUnit.disabled = false;

  const prevUnit = state.unit || '';
  const units = getUnitsForCurrentFreq();
  const allUnits = getAllUnits();

  if (!allUnits.length) {
    state.unit = '';
    selUnit.innerHTML = '';
    selUnit.disabled = true;
    setLockMsg('No existen unidades disponibles para la frecuencia seleccionada.');
    el('gridEmpty').textContent = 'Sin unidades.';
    el('gridEmpty').style.display = 'flex';
    el('gridScroll').style.display = 'none';
    return;
  }

  const validSet = new Set(units);
  allUnits.forEach(u => {
    const opt = document.createElement('option');
    opt.value = u; opt.textContent = u;
    opt.disabled = !validSet.has(u);
    selUnit.appendChild(opt);
  });

  if (!units.length) {
    state.unit = '';
    selUnit.disabled = true;
    selUnit.value = '';
    setText('unitVal', '');
    setLockMsg('No existen unidades disponibles para la frecuencia seleccionada.');
    el('gridEmpty').textContent = 'Sin unidades.';
    el('gridEmpty').style.display = 'flex';
    el('gridScroll').style.display = 'none';
    return;
  }

  let nextUnit = '';
  let autoMsg = '';
  if (forceFirstUnit && units.length) {
    nextUnit = units[0];
  } else if (prevUnit && validSet.has(prevUnit)) {
    nextUnit = prevUnit;
  } else if (units.length === 1) {
    nextUnit = units[0];
  } else if (prevUnit) {
    nextUnit = units[0];
    autoMsg = 'Unidad ajustada automáticamente para la frecuencia seleccionada.';
  }

  state.unit = nextUnit;
  selUnit.value = nextUnit;
    setText('unitVal', state.unit || '');

  if (!state.unit) {
    setLockMsg('Seleccione unidad para visualizar el cuadro.');
    el('gridEmpty').textContent = 'Selecciona una unidad.';
    el('gridEmpty').style.display = 'flex';
    el('gridScroll').style.display = 'none';
    return;
  }

  setLockMsg(autoMsg || null);
  await loadGrid();
  return;

}

/* ---------------- Grid ---------------- */

async function loadGrid() {
  if (!state.activeGrupo || !state.freq || !state.unit) return;
  if (!isValidUnitForFreq(state.unit, state.freq)) {
    setLockMsg('Unidad inválida para la frecuencia seleccionada.');
    return;
  }
  const reqSeq = ++loadGridSeq;
  const expected = {
    id: state.activeGrupo,
    freq: state.freq,
    unit: state.unit,
    desde: state.range.desde,
    hasta: state.range.hasta,
  };

  el('gridEmpty').textContent = 'Cargando datos...';
  el('gridEmpty').style.display = 'flex';
  el('gridScroll').style.display = 'none';

  try {
    const id = expected.id;
    const f = expected.freq;
    const u = expected.unit;
    const d = expected.desde;
    const h = expected.hasta;
    const g = await getJson(restApiUrl('grid', { id_grupo: id, frecuencia: f, unidad: u, desde: d, hasta: h }));
    if (
      reqSeq !== loadGridSeq ||
      state.activeGrupo !== expected.id ||
      state.freq !== expected.freq ||
      state.unit !== expected.unit ||
      state.range.desde !== expected.desde ||
      state.range.hasta !== expected.hasta
    ) return;
    state.grid = g;

    renderGrid();
    if (perf.enabled && !perf.firstGrid) {
      perf.firstGrid = true;
      perfMark('first grid rendered', { rows: (state.grid.rows || []).length, cols: (state.grid.columns || []).length });
    }

    // botón agregar (canasta +) habilitado si hay marcados
    syncAddToCartButton();
    // No auto-add series to collection on first load.

  } catch (e) {
    if (reqSeq !== loadGridSeq) return;
    setLockMsg(`Error grid: ${e.message}`);
    el('gridEmpty').textContent = 'Error al cargar el cuadro.';
  }
}

function isInCollection(token) {
  return state.collection.some(it => it.token === token && it.frecuencia === state.freq && it.unidad === state.unit);
}

function renderGrid() {
  const gridEl = el('grid');
  const columns = state.grid.columns || [];
  const rows = state.grid.rows || [];
  const collectionTokens = new Set(
    state.collection
      .filter(it => it.frecuencia === state.freq && it.unidad === state.unit)
      .map(it => it.token)
  );

  if (!rows.length || !columns.length) {
    el('gridEmpty').textContent = 'Sin datos para los filtros seleccionados.';
    el('gridEmpty').style.display = 'flex';
    el('gridScroll').style.display = 'none';
    return;
  }

  let html = '<thead><tr>';
  html += `<th class="sticky col-serie">`+
          `<div class="head-left">`+
          `<input id="chkAll" class="chk" type="checkbox" data-bce-tooltip="Seleccionar todas">`+
          `<span>Seleccionar todo</span>`+
          `</div>`+
          `</th>`;
  columns.forEach(c => html += `<th>${escapeHtml(c)}</th>`);
  html += '</tr></thead><tbody>';

  const hasCabeceras = rows.some(x => String(x.tipo) === 'Cabeceras');
  let lastCabeceraIdx = -1;
  let lastTopSeriesIdx = -1;
  rows.forEach((r, idx) => {
    if (r.tipo === 'Cabeceras') {
      lastCabeceraIdx = idx;
      html += `<tr class="row-cab">`;
      const isSub = Number(r.nivel) > 0;
    html += `<td class="sticky col-serie${isSub ? ' col-serie-sub' : ''}">${indentLabel(r.label, r.nivel)}</td>`;
      columns.forEach(_ => html += `<td></td>`);
      html += `</tr>`;
      return;
    }

    if (hasCabeceras && r.tipo === 'Series' && Number(r.nivel) === 1) {
      if (lastCabeceraIdx > lastTopSeriesIdx) {
        html += `<tr class="row-sep"><td colspan="${columns.length + 1}"></td></tr>`;
      }
      lastTopSeriesIdx = idx;
    }

    const token = r.token;
    const inColl = collectionTokens.has(token);
    // Si ya está en colección, el checkbox queda visible pero deshabilitado.
    const checked = (inColl || state.marked.has(token)) ? 'checked' : '';
    const disabled = inColl ? 'disabled' : '';

    const isFocus = pendingFocusToken && token === pendingFocusToken;
    html += `<tr${isFocus ? ' class="row-focus"' : ''} data-token="${escapeHtml(token)}">`;
    const isSub = Number(r.nivel) > 0;
    html += `<td class="sticky col-serie${isSub ? ' col-serie-sub' : ''}">
      <div class="cell-actions">
        <input class="chk" type="checkbox" data-token="${token}" ${checked} ${disabled}>
        <button class="graph-mini" data-chart="${token}" data-bce-tooltip="Graficar serie" aria-label="Graficar serie"></button>
        <button class="info" data-info="${token}" data-bce-tooltip="Metadatos" aria-label="Metadatos">i</button>
        <div style="flex:1">${indentLabel(wrapLabel(r.label, 90), r.nivel, { html: true })}</div>
      </div>
    </td>`;

    columns.forEach(c => {
      const v = r.values ? r.values[c] : null;
      html += `<td>${fmtNumberEs(v)}</td>`;
    });

    html += `</tr>`;
  });

  html += '</tbody>';
  gridEl.innerHTML = html;
  promoteInstantTooltips(gridEl);

  el('gridEmpty').style.display = 'none';
  el('gridScroll').style.display = 'block';
  if (pendingFocusToken) {
    const targetRow = gridEl.querySelector(`tr[data-token="${CSS.escape(pendingFocusToken)}"]`);
    if (targetRow) {
      targetRow.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    pendingFocusToken = null;
  }

  // Seleccionar todas (solo disponibles; no incluye deshabilitadas)
  const chkAll = el('chkAll');
  if (chkAll) {
    const candidates = Array.from(gridEl.querySelectorAll('input[type="checkbox"][data-token]'));
    const updateAllState = () => {
      const eligible = candidates.filter(c => !c.disabled);
      const marked = eligible.filter(c => c.checked).length;
      if (!eligible.length) {
        chkAll.checked = false;
        chkAll.indeterminate = false;
        chkAll.disabled = true;
        syncAddToCartButton();
        return;
      }
      chkAll.disabled = false;
      chkAll.checked = marked === eligible.length;
      chkAll.indeterminate = marked > 0 && marked < eligible.length;
    };
    // inicial
    updateAllState();
    gridUpdateAllState = updateAllState;
  }
}

/* ---------------- Collection ---------------- */

function addMarkedToCollection() {
  if (!state.unit || !state.freq) return;

  // regla: no agregar si unidad no seleccionada (A1)
  if (!state.unit) {
    setLockMsg('Seleccione unidad antes de agregar series a la colecci\u00F3n.');
    return;
  }

  const rows = state.grid.rows || [];
  const tokenToRow = new Map(rows.filter(r=>r.tipo==='Series').map(r=>[r.token, r]));

  let added = 0;
  for (const token of state.marked) {
    const row = tokenToRow.get(token);
    if (!row) continue;

    // evitar duplicados por token+freq+unit
    const exists = state.collection.some(it => it.token === token && it.frecuencia === state.freq && it.unidad === state.unit);
    if (exists) continue;

    state.collection.push({
      token,
      label: row.label,
      ruta: row.ruta || '',
      cuadro: `${state.bundle?.context?.cod_grupo || ''} ${state.bundle?.context?.nom_grupo || ''}`.trim(),
      rango: (() => {
        const r = getRangeForFreq(state.freq);
        return { minYm: r?.minYm || null, maxYm: r?.maxYm || null, freq: state.freq };
      })(),
      unidad: state.unit,
      frecuencia: state.freq,
      graph: false,
    });
    added++;
  }

  // limpiar marcados y refrescar grid para bloquear los ya agregados
  state.marked = new Set();
  syncAddToCartButton();

  updateCollectionUI();
  renderGrid(); // refresca estados "En colección"

  // habilitar acciones
  el('btnDownloadSeries').disabled = state.collection.length === 0;
  el('btnClearSeries').disabled = state.collection.length === 0;


  if (added === 0) return;
}

function updateCollectionUI() {
  const c = el('collection');
  c.innerHTML = '';

  el('collCount').textContent = String(state.collection.length);
  el('btnClearSeries').disabled = state.collection.length === 0;
  el('btnDownloadSeries').disabled = state.collection.length === 0;
  syncCollectionRangeFromCollection(!state.collectionRange?.desde);

  if (!state.collection.length) {
    c.classList.add('collection-empty');
    c.textContent = 'Selecciona tus series de todos los cuadros y agr\u00E9galas aqu\u00ED.';
    return;
  }
  c.classList.remove('collection-empty');

  const btnSortCuadro = el('btnSortCuadro');
  const btnSortFrecuencia = el('btnSortFrecuencia');
  const btnSortUnidad = el('btnSortUnidad');
  if (btnSortCuadro && btnSortFrecuencia && btnSortUnidad) {
    const isCuadro = state.collectionSort === 'cuadro';
    const isFreq = state.collectionSort === 'frecuencia';
    const isUnidad = state.collectionSort === 'unidad';
    btnSortCuadro.classList.toggle('is-active', isCuadro);
    btnSortCuadro.setAttribute('aria-pressed', isCuadro ? 'true' : 'false');
    btnSortFrecuencia.classList.toggle('is-active', isFreq);
    btnSortFrecuencia.setAttribute('aria-pressed', isFreq ? 'true' : 'false');
    btnSortUnidad.classList.toggle('is-active', isUnidad);
    btnSortUnidad.setAttribute('aria-pressed', isUnidad ? 'true' : 'false');
  }

  const items = [...state.collection];
  if (state.collectionSort === 'frecuencia') {
    items.sort((a, b) => {
      const af = (a.frecuencia || '').localeCompare(b.frecuencia || '', 'es');
      if (af !== 0) return af;
      return (a.label || '').localeCompare(b.label || '', 'es');
    });
  } else if (state.collectionSort === 'unidad') {
    items.sort((a, b) => {
      const au = (a.unidad || '').localeCompare(b.unidad || '', 'es');
      if (au !== 0) return au;
      return (a.label || '').localeCompare(b.label || '', 'es');
    });
  } else {
    items.sort((a, b) => {
      const ac = (a.cuadro || '').localeCompare(b.cuadro || '', 'es');
      if (ac !== 0) return ac;
      return (a.label || '').localeCompare(b.label || '', 'es');
    });
  }

  items.forEach(it => {
    const div = document.createElement('div');
    div.className = 'item';

    // indicador de color (si está activa para graficar)
    const dot = document.createElement('div');
    dot.className = 'dot';
    dot.textContent = '';
    if (it.graph) {
      const c = ensureColor(it.token, it.frecuencia);
      dot.style.background = c;
    }

    const main = document.createElement('div');
    const txtColor = it.graph ? ensureColor(it.token, it.frecuencia) : '';
    let rangoText = '';
    if (it.rango && typeof it.rango === 'object') {
      rangoText = formatRangeAvailable(it.rango.freq || it.frecuencia, it.rango.minYm, it.rango.maxYm);
    } else if (it.rango) {
      rangoText = `rango disponible: ${it.rango}`;
    }
    const cuadroText = it.cuadro || '';
    const rutaText = it.ruta || '';
      main.innerHTML = `
        <div class="series-head"><span class="series-name" style="color:${txtColor}">${escapeHtml(it.label)}</span><span class="meta">(${escapeHtml(it.frecuencia)})</span></div>
        <div class="ruta">cuadro: ${escapeHtml(cuadroText)}</div>
        <div class="cuadro-meta">ruta: ${escapeHtml(rutaText)}</div>
        ${rangoText ? `<div class="cuadro-meta">${escapeHtml(rangoText)}</div>` : ''}
      `;

    const unit = document.createElement('div');
    unit.className = 'unit';
    unit.textContent = it.unidad;

    const graph = document.createElement('button');
    graph.className = 'graphbtn' + (it.graph ? ' active' : '');
    graph.textContent = '';
    graph.setAttribute('aria-label', 'Graficar (máx. 10)');
    graph.setAttribute('data-bce-tooltip', 'Graficar (máx. 10)');
    graph.addEventListener('click', () => toggleGraphItem(it));

    const trash = document.createElement('button');
    trash.className = 'trash';
    trash.textContent = '';
    trash.setAttribute('aria-label', 'Eliminar de colección');
    trash.setAttribute('data-bce-tooltip', 'Eliminar de colección');
    trash.addEventListener('click', () => {
      // quitar y mantener marcado/checkbox del grid como estaba (G1)
      const wasGraphed = !!it.graph;
      state.collection = state.collection.filter(x => !(x.token===it.token && x.frecuencia===it.frecuencia && x.unidad===it.unidad));
      updateCollectionUI();
      renderGrid(); // libera checkbox
      if (wasGraphed) refreshChart();
    });

    div.appendChild(dot);
    div.appendChild(main);
    div.appendChild(unit);
    div.appendChild(graph);
    div.appendChild(trash);

    c.appendChild(div);
  });
}

function addSeriesToCollection(row, graphOn) {
  if (!row || !state.unit || !state.freq) return false;
  const token = row.token;
  if (!token) return false;
  const exists = state.collection.some(it => it.token === token && it.frecuencia === state.freq && it.unidad === state.unit);
  if (exists) return false;

  const item = {
    token,
    label: row.label,
    ruta: row.ruta || '',
    cuadro: `${state.bundle?.context?.cod_grupo || ''} ${state.bundle?.context?.nom_grupo || ''}`.trim(),
    rango: (() => {
      const r = getRangeForFreq(state.freq);
      return { minYm: r?.minYm || null, maxYm: r?.maxYm || null, freq: state.freq };
    })(),
    unidad: state.unit,
    frecuencia: state.freq,
    graph: !!graphOn,
  };
  if (item.graph) ensureColor(item.token, item.frecuencia);
  state.collection.push(item);
  return true;
}

async function autoInitCuadro111() {
  if (state.autoInitDone) return;
  if (state.activeGrupo !== 35) return;
  const rows = state.grid.rows || [];
  const firstSerie = rows.find(r => r.tipo === 'Series');
  if (!firstSerie) return;
  const added = addSeriesToCollection(firstSerie, false);
  if (!added) return;
  state.autoInitDone = true;
  updateCollectionUI();
  renderGrid();
}

async function syncCollectionRangeFromCollection(forceReset) {
  if (!state.collection.length) {
    setCollectionRangeFull(null, true);
    return;
  }

  const range = await fetchFullGraphRange(state.collection);
  const shouldReset = !!forceReset && !(state.collectionRange?.desde && state.collectionRange?.hasta);
  if (range?.desde && range?.hasta) {
    setCollectionRangeFull(range, shouldReset);
    return;
  }

  if (state.range?.desde && state.range?.hasta) {
    const fallback = { desde: state.range.desde, hasta: state.range.hasta };
    setCollectionRangeFull(fallback, shouldReset);
  }
}

function clearCollection() {
  state.collection = [];
  state.marked = new Set();
  updateCollectionUI();
  renderGrid();
  refreshChart();
}

/* ---------------- Chart ---------------- */

function ensureChartContainer() {
  const box = el('chartBox');
  if (state.chartOn) {
    box.className = 'chart';
    box.innerHTML = `
      <div id="chart"></div>
    `;
  } else {
    box.className = 'chart-empty';
    box.innerHTML = `<div class="chart-empty-msg">Active el gr\u00e1fico y seleccione series en la colecci\u00f3n.</div>`;
  }
  ensureChartQuickButtons(false);
}

function activeGraphItems() {
  return state.collection.filter(it => it.graph);
}

function ensureChartQuickButtons(enabled) {
  const box = el('chartBox');
  if (!box) return;
  let wrap = el('chartQuickRange');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.id = 'chartQuickRange';
    wrap.className = 'chart-quick-range';
    wrap.innerHTML = `
      <button class="chart-quick-btn" type="button" data-months="60">\u00DAltimos 5 a\u00F1os</button>
      <button class="chart-quick-btn" type="button" data-months="12">\u00DAltimo a\u00F1o</button>
    `;
    wrap.addEventListener('click', (ev) => {
      const btn = ev.target.closest ? ev.target.closest('button[data-months]') : null;
      if (!btn) return;
      const months = Number(btn.getAttribute('data-months') || 0);
      if (months > 0) applyQuickChartRange(months);
    });
    box.appendChild(wrap);
  }
  const btns = wrap.querySelectorAll('button');
  btns.forEach(b => { b.disabled = !enabled; });
  wrap.classList.toggle('is-disabled', !enabled);
}

async function fetchFullGraphRange(items) {
  if (!items.length) return null;
  const key = items
    .map(it => `${it.token}::${it.frecuencia}`)
    .sort()
    .join('|');
  if (chartRangeCache.has(key)) return chartRangeCache.get(key);
  if (chartRangeInFlight.has(key)) return chartRangeInFlight.get(key);
  const payloadItems = items.map(it => ({ token: it.token, frecuencia: it.frecuencia }));
  const req = (async () => {
    try {
      const resp = await postJson(restApiUrl('chart-range'), { items: payloadItems }, { withNonce: false });
      if (resp?.minYm && resp?.maxYm) {
        const out = { desde: resp.minYm, hasta: resp.maxYm };
        chartRangeCache.set(key, out);
        if (chartRangeCache.size > 20) chartRangeCache.clear();
        return out;
      }
    } catch (e) {
      return null;
    }
    return null;
  })();
  chartRangeInFlight.set(key, req);
  try {
    return await req;
  } finally {
    chartRangeInFlight.delete(key);
  }
}

function fillYearSelect(selectEl, minY, maxY, selectedY) {
  if (!selectEl) return;
  selectEl.innerHTML = '';
  if (!minY || !maxY) return;
  for (let y = minY; y <= maxY; y++) {
    const opt = document.createElement('option');
    opt.value = String(y);
    opt.textContent = String(y);
    if (selectedY && String(selectedY) === String(y)) opt.selected = true;
    selectEl.appendChild(opt);
  }
}

async function getCollectionYearRange() {
  if (!state.collection.length) return null;
  const items = state.collection.map(it => ({ token: it.token, frecuencia: it.frecuencia }));
  try {
    const resp = await postJson(restApiUrl('chart-range'), { items }, { withNonce: false });
    if (resp?.minYm && resp?.maxYm) {
      const minY = ymToYear(resp.minYm);
      const maxY = ymToYear(resp.maxYm);
      if (minY && maxY) return { minY, maxY };
    }
  } catch (e) {
    return null;
  }
  return null;
}

async function toggleGraphItem(item) {
  // Regla unidad: no mezclar unidades en gráfico (A1)
  const active = activeGraphItems();
  const unitActive = active.length ? active[0].unidad : null;

  if (!item.graph) {
    // activar
    if (unitActive && unitActive !== item.unidad) {
      setLockMsg('No se permite graficar series con unidades distintas. Desactive las series actuales o seleccione otra.');
      return;
    }
    if (active.length >= 10) {
      setLockMsg('Maximo 10 series para graficar. Puede ampliar la ventana para mejorar la visualización del gráfico.');
      return;
    }
    item.graph = true;
    ensureColor(item.token, item.frecuencia);
  } else {
    // desactivar
    item.graph = false;
  }

  // limpiar mensaje si ya cumple
  const act2 = activeGraphItems();
  if (!act2.length) setLockMsg(state.lockMsg && state.lockMsg.includes('unidades') ? null : state.lockMsg);
  updateCollectionUI();
  refreshChart();
}

async function refreshChart() {
  ensureChartContainer();

  if (!state.chartOn) {
    if (state.chart) { state.chart.destroy(); state.chart = null; }
    return;
  }

  const items = activeGraphItems();
  if (!items.length) {
    if (state.chart) { state.chart.destroy(); state.chart = null; }
    el('chartBox').className = 'chart-empty';
    el('chartBox').innerHTML = `<div class="chart-empty-msg">Selecciona hasta 10 series para graficarlas</div>`;
    ensureChartQuickButtons(false);
    return;
  }

  const unidad = items[0].unidad; // ya validado
  const payloadItems = items.map(it => ({ token: it.token, frecuencia: it.frecuencia }));

  try {
    if (!window.Highcharts) throw new Error('Highcharts no disponible.');
    const full = await fetchFullGraphRange(items);
    let range = (state.chartRange.desde && state.chartRange.hasta)
      ? state.chartRange
      : (state.collectionRange?.desde && state.collectionRange?.hasta)
        ? state.collectionRange
        : (full || state.range);
    if (!range?.desde || !range?.hasta) {
      const fb = getRangeForCurrentFreq();
      if (fb?.minYm && fb?.maxYm) range = { desde: fb.minYm, hasta: fb.maxYm };
    }
    if (!range?.desde || !range?.hasta) {
      setLockMsg('Defina un rango válido para graficar.');
      return;
    }
    const resp = await postJson(restApiUrl('chart'), {
      items: payloadItems,
      unidad,
      desde: range.desde,
      hasta: range.hasta,
    }, { withNonce: false });

    const raw = resp.series || [];

    // Tipos por frecuencia: si hay una sola frecuencia => línea; si hay varias => tipos distintos
    const freqs = Array.from(new Set(raw.map(s => s.freq).filter(Boolean)));
    const pool = ['line','column','area','spline'];
    const typeByFreq = {};
    if (freqs.length <= 1) {
      if (freqs[0]) typeByFreq[freqs[0]] = 'line';
    } else {
      freqs.forEach((f,i) => { typeByFreq[f] = pool[i % pool.length]; });
    }
    const chartFreqLabelMode = freqs.length === 1 ? freqs[0] : '';

    // Aplicar color consistente por serie activada (token|frecuencia)
    const series = raw.map(s => {
      const key = `${s.token}|${s.freq}`;
      const c = state.colorMap.get(key) || ensureColor(s.token, s.freq);
      return {
        name: s.name,
        freq: s.freq,
        type: typeByFreq[s.freq] || 'line',
        color: c,
        data: s.data || [],
      };
    });
    const chartDiv = document.getElementById('chart');
    if (!chartDiv) return;

    const opt = {
      chart: {
        zoomType: 'x',
        events: {
          fullscreenOpen: function () {
            this.update({ legend: { enabled: true } }, false);
            this.redraw();
          },
          fullscreenClose: function () {
            this.update({ legend: { enabled: false } }, false);
            this.redraw();
          }
        }
      },
      title: { text: '' },
      credits: { enabled: false },
      rangeSelector: { enabled: false },
      navigator: { enabled: true },
      scrollbar: { enabled: true },
      xAxis: { type: 'datetime', ordinal: false },
      yAxis: { title: { text: '' } },
      legend: { enabled: false },
      tooltip: {
        shared: true,
        formatter: function () {
          const pts = this.points || [];
          if (!pts.length) return '';
          const freqs = Array.from(new Set(pts.map(p => p.series?.options?.freq).filter(Boolean)));
          let header = '';
          if (freqs.length === 1) header = formatTooltipDateByFreq(freqs[0], this.x);
          let out = header ? `<span>${header}</span><br/>` : '';
          pts.forEach(p => {
            const f = p.series?.options?.freq;
            const dateStr = freqs.length > 1 ? formatTooltipDateByFreq(f, p.x) : '';
            const val = Highcharts.numberFormat(p.y, 2, '.', ',');
            out += `<span style="color:${p.color}">\u25CF</span> ${p.series.name}: <b>${val}</b>`;
            if (dateStr) out += ` <span style="color:#666">(${dateStr})</span>`;
            out += '<br/>';
          });
          return out;
        }
      },
      plotOptions: {
        series: { marker: { enabled: false }, turboThreshold: 0 },
        column: { pointPadding: 0.05, groupPadding: 0.1 }
      },
      series,
      exporting: getExportingOptions()
    };

    if (state.chart) state.chart.destroy();
    state.chart = (Highcharts.stockChart ? Highcharts.stockChart('chart', opt) : Highcharts.chart('chart', opt));
    setTimeout(() => { if (state.chart && state.chart.reflow) state.chart.reflow(); }, 0);
    ensureChartQuickButtons(true);

  } catch (e) {
    setLockMsg(`Error gráfico: ${e.message}`);
  }
}

/* ---------------- Meta popover (anclado al ícono info) ---------------- */

function getFsMetaPopover() {
  let p = el('metaPopoverFs');
  if (p) return p;
  const host = document.querySelector('.panel-left');
  if (!host) return null;
  p = document.createElement('div');
  p.id = 'metaPopoverFs';
  p.className = 'popover';
  p.style.display = 'none';
  host.appendChild(p);
  return p;
}

function hideMetaPopover() {
  const p = el('metaPopover');
  if (p) {
    p.style.display = 'none';
    p.innerHTML = '';
  }
  const pf = el('metaPopoverFs');
  if (pf) {
    pf.style.display = 'none';
    pf.innerHTML = '';
  }
}

async function openMeta(token, anchorEl) {
  if (!state.freq || !state.unit) {
    setLockMsg('Seleccione frecuencia y unidad para ver metadatos.');
    return;
  }
  const inFs = isGridFullscreen();
  const host = inFs ? document.querySelector('.panel-left') : null;
  const pop = (inFs && host) ? getFsMetaPopover() : el('metaPopover');
  if (!pop || !anchorEl) return;
  try {
    const m = await getJson(restApiUrl('meta', { token, frecuencia: state.freq, unidad: state.unit }));

    pop.style.zIndex = inFs ? '99999' : '60';
    pop.style.position = 'absolute';
    pop.style.transform = '';
      pop.classList.add('meta-pop');
      const metaVal = (v) => {
        if (v === 0) return '0';
        const s = repairMojibakeText((v ?? '').toString()).trim();
        return s === '' ? '-' : s;
      };
      const defRaw = metaVal(m.definicion || m.descripcion || '');
      pop.innerHTML = `
        <div class="meta-head"><div class="t">Metadatos de la serie</div><button class="x" type="button" data-bce-tooltip="Cerrar" aria-label="Cerrar">x</button></div>
        <div class="meta-grid">
        <div class="k">Cuadro</div><div class="v">${escapeHtml(metaVal(m.cuadro || ''))}</div>
        <div class="k">Nombre de serie</div><div class="v">${escapeHtml(metaVal(m.nombre_serie || m.nom_serie || ''))}</div>
        <div class="k">Definici\u00f3n</div>
          <div class="v meta-def">
            <span class="meta-def-text">${escapeHtml(defRaw)}</span>
            <button class="meta-def-more" type="button" aria-expanded="false" data-bce-tooltip="Ver definici\u00F3n completa">Ver m\u00E1s</button>
          </div>
        <div class="k">Fuente</div><div class="v">${escapeHtml(metaVal(m.fuente || ''))}</div>
        <div class="k">Sector</div><div class="v">${escapeHtml(metaVal(m.sector || ''))}</div>
        <div class="k">A\u00f1o base</div><div class="v">${escapeHtml(metaVal(m.aniobase ?? ''))}</div>
        <div class="k">Fecha Manual</div><div class="v">${escapeHtml(metaVal(m.fecha_manual || ''))}</div>
        <div class="k">Nombre Manual</div><div class="v">${escapeHtml(metaVal(m.nombre_manual || ''))}</div>
        <div class="k">Revisi\u00F3n</div><div class="v">${escapeHtml(metaVal(m.revision || ''))}</div>
        <div class="k">Rezago</div><div class="v">${escapeHtml(metaVal(m.rezago !== '' && m.rezago !== null && m.rezago !== undefined ? `${m.rezago} d\u00EDas` : ''))}</div>
        <div class="k">Tipo de dato</div><div class="v">${escapeHtml(metaVal(m.tipodato || ''))}</div>
        <div class="k">Fecha de actualización</div><div class="v">${escapeHtml(metaVal((m.fecha_actualiza || '').toString().split(' ')[0]))}</div>
        <div class="k">Link</div><div class="v">${escapeHtml(metaVal(m.link || ''))}</div>
        <div class="k">Ruta</div><div class="v">${escapeHtml(metaVal(m.ruta || ''))}</div>
        <div class="k">Unidad</div><div class="v">${escapeHtml(metaVal(m.unidad || ''))}</div>
        <div class="k">Frecuencia</div><div class="v">${escapeHtml(metaVal(m.frecuencia || ''))}</div>
        <div class="k">Ultimo valor</div><div class="v">${m.ultimo_valor === null ? '-' : escapeHtml(fmtNumberEs(m.ultimo_valor))}</div>
        <div class="k">Fecha ultimo dato</div><div class="v">${escapeHtml(m.fecha_ultimo_dato ? m.fecha_ultimo_dato.toString().slice(0, 7) : '-')}</div>
        </div>
      `;
      const closeBtn = pop.querySelector('button.x');
      if (closeBtn) closeBtn.addEventListener('click', (ev) => { ev.stopPropagation(); hideMetaPopover(); });
      const defBtn = pop.querySelector('.meta-def-more');
      const defText = pop.querySelector('.meta-def-text');
      if (defBtn) {
        if (defRaw.length < 160 || defRaw === '-') {
          defBtn.style.display = 'none';
          if (defText) defText.classList.add('meta-def-text--full');
        } else {
          defBtn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            let tip = pop.querySelector('.meta-def-pop');
            if (tip) {
              tip.remove();
              defBtn.setAttribute('aria-expanded', 'false');
              return;
            }
            tip = document.createElement('div');
            tip.className = 'meta-def-pop';
            tip.innerHTML = `
              <div class="meta-def-pop-head">
                <span>Definici\u00f3n completa</span>
                <button type="button" class="meta-def-pop-close" data-bce-tooltip="Cerrar" aria-label="Cerrar">x</button>
              </div>
              <div class="meta-def-pop-body"></div>
            `;
            tip.querySelector('.meta-def-pop-body').textContent = defRaw;
            pop.appendChild(tip);
            defBtn.setAttribute('aria-expanded', 'true');
            const pr = pop.getBoundingClientRect();
            const br = defBtn.getBoundingClientRect();
            const top = Math.max(8, br.bottom - pr.top + 4);
            const left = Math.max(10, Math.min((br.left - pr.left) + 10, Math.max(10, pr.width - 260)));
            tip.style.top = `${top}px`;
            tip.style.left = `${left}px`;
            tip.style.right = 'auto';
            const close = tip.querySelector('.meta-def-pop-close');
            if (close) close.addEventListener('click', (e) => { e.stopPropagation(); tip.remove(); defBtn.setAttribute('aria-expanded', 'false'); });
          });
        }
      }
      pop.style.display = 'block';

    // Posicionar: encima y hacia la izquierda del icono (como Banxico)
    const r = anchorEl.getBoundingClientRect();
    // medir después de render
    const w = pop.offsetWidth;
    const h = pop.offsetHeight;
    const pad = 8;
    if (inFs && host) {
      const hr = host.getBoundingClientRect();
      let left = r.left - hr.left - w + r.width;
      let top  = r.top - hr.top - h - pad;
      if (left < 8) left = 8;
      if (top < 8) top = r.bottom - hr.top + pad;
      const maxLeft = host.clientWidth - w - 8;
      if (Number.isFinite(maxLeft) && maxLeft >= 8 && left > maxLeft) left = maxLeft;
      pop.style.left = `${left}px`;
      pop.style.top  = `${top}px`;
    } else {
      let left = window.scrollX + r.left - w + r.width;
      let top  = window.scrollY + r.top - h - pad;
      if (left < window.scrollX + 8) left = window.scrollX + 8;
      if (top < window.scrollY + 8) top = window.scrollY + r.bottom + pad;
      pop.style.left = `${left}px`;
      pop.style.top  = `${top}px`;
    }

  } catch (e) {
    setLockMsg(`Error metadatos: ${e.message}`);
  }
}

/* ---------------- Series chart modal ---------------- */

function getChartRangeDefaults() {
  const r = getRangeForFreq(seriesChartCtx?.frecuencia || state.freq);
  const minYm = r.minYm || '';
  const maxYm = r.maxYm || '';
  const desde = state.range.desde || minYm || '';
  const hasta = state.range.hasta || maxYm || '';
  return { desde, hasta, minYm, maxYm };
}

function openSeriesChartModal(token) {
  if (!state.freq || !state.unit) {
    setLockMsg('Seleccione frecuencia y unidad para graficar.');
    return;
  }
  const row = (state.grid.rows || []).find(r => r.tipo === 'Series' && r.token === token);
  const label = row?.label || 'Serie';
  seriesChartCtx = { token, frecuencia: state.freq, unidad: state.unit, label };

  setText('chartModalTitle', label);
  const { desde, hasta } = getChartRangeDefaults();
  applySeriesCalendarMode(seriesChartCtx.frecuencia, desde, hasta);
  el('chartModal').style.display = 'flex';
  loadSeriesChart();
}

function closeSeriesChartModal() {
  el('chartModal').style.display = 'none';
  if (seriesChart) {
    seriesChart.destroy();
    seriesChart = null;
  }
  seriesChartCtx = null;
}

async function loadSeriesChart() {
  if (!seriesChartCtx) return;
  let rangeState = getSeriesRangeInputState(seriesChartCtx.frecuencia);
  if (rangeState.error === 'order') {
    setLockMsg('Rango inválido: Desde > Hasta.');
    return;
  }
  let parsed = rangeState.parsed;
  if (!parsed) {
    const fallback = await fetchFullGraphRange([{ token: seriesChartCtx.token, frecuencia: seriesChartCtx.frecuencia }]);
    if (fallback?.desde && fallback?.hasta) {
      applySeriesCalendarMode(seriesChartCtx.frecuencia, fallback.desde, fallback.hasta);
      rangeState = getSeriesRangeInputState(seriesChartCtx.frecuencia);
      parsed = rangeState.parsed;
    }
    if (!parsed) {
      const fb = getRangeForFreq(seriesChartCtx.frecuencia);
      if (fb?.minYm && fb?.maxYm) {
        applySeriesCalendarMode(seriesChartCtx.frecuencia, fb.minYm, fb.maxYm);
        rangeState = getSeriesRangeInputState(seriesChartCtx.frecuencia);
        parsed = rangeState.parsed;
      }
    }
    if (!parsed) {
      setLockMsg('Defina rango desde/hasta.');
      return;
    }
  }
  if (parsed.desde > parsed.hasta) {
    setLockMsg('Rango inválido: Desde > Hasta.');
    return;
  }
  const { desde, hasta } = parsed;

  try {
    if (!window.Highcharts) throw new Error('Highcharts no disponible.');
    const resp = await postJson(restApiUrl('chart'), {
      items: [{ token: seriesChartCtx.token, frecuencia: seriesChartCtx.frecuencia }],
      unidad: seriesChartCtx.unidad,
      desde,
      hasta,
    }, { withNonce: false });
    const series = resp.series || [];
    const s0 = series[0] || {};
    const data = s0.data || [];

    const opt = {
      chart: { type: 'line', zoomType: 'x' },
      title: { text: '' },
      credits: { enabled: false },
      xAxis: { type: 'datetime' },
      yAxis: { title: { text: '' } },
      legend: { enabled: false },
      tooltip: {
        shared: false,
        formatter: function () {
          const f = seriesChartCtx?.frecuencia || '';
          const dateStr = formatTooltipDateByFreq(f, this.x);
          const val = Highcharts.numberFormat(this.y, 2, '.', ',');
          return `<span>${dateStr}</span><br/><b>${val}</b>`;
        }
      },
      series: [{ name: seriesChartCtx.label, data }],
      exporting: getExportingOptions()
    };

    if (seriesChart) seriesChart.destroy();
    seriesChart = Highcharts.chart('chartSeries', opt);
    setTimeout(() => { if (seriesChart && seriesChart.reflow) seriesChart.reflow(); }, 0);
  } catch (e) {
    setLockMsg(`Error gráfico: ${e.message}`);
  }
}

/* ---------------- Download collection panel ---------------- */

async function openDownloadPanel() {
  if (!state.bundle) return;
  const dlDesde = el('dlDesde');
  const dlHasta = el('dlHasta');
  const dlPanel = el('dlPanel');
  const titleEl = dlPanel ? dlPanel.querySelector('.modal-title') : null;
  if (titleEl) titleEl.textContent = `Descargar colección de ${state.collection.length} series`;
  let minY = null;
  let maxY = null;
  let selDesdeY = null;
  let selHastaY = null;
  const selRange = (state.collectionRange?.desde && state.collectionRange?.hasta) ? state.collectionRange : null;
  const fullRange = (state.collectionRangeFull?.desde && state.collectionRangeFull?.hasta) ? state.collectionRangeFull : null;
  if (fullRange) {
    minY = ymToYear(fullRange.desde);
    maxY = ymToYear(fullRange.hasta);
  }
  if (selRange) {
    selDesdeY = ymToYear(selRange.desde);
    selHastaY = ymToYear(selRange.hasta);
  }
  if (!minY || !maxY) {
    const rng = await getCollectionYearRange();
    if (rng) {
      minY = rng.minY;
      maxY = rng.maxY;
    } else {
      minY = ymToYear(state.range.desde);
      maxY = ymToYear(state.range.hasta);
    }
  }
  if (!selDesdeY) selDesdeY = minY;
  if (!selHastaY) selHastaY = maxY;
  fillYearSelect(dlDesde, minY, maxY, selDesdeY);
  fillYearSelect(dlHasta, minY, maxY, selHastaY);
  el('dlMeta').checked = false;
  el('dlFmt').value = 'csv';
  if (dlPanel) dlPanel.classList.toggle('dl-compact', !!(minY && maxY));
  el('dlPanel').style.display = 'flex';
}

function closeDownloadPanel() {
  el('dlPanel').style.display = 'none';
}

async function doDownloadCollection() {
  const yDesde = el('dlDesde').value;
  const yHasta = el('dlHasta').value;
  const withMeta = el('dlMeta').checked;
  const fmt = el('dlFmt').value;

  if (!yDesde || !yHasta) { setLockMsg('Defina rango desde/hasta.'); return; }
  if (Number(yDesde) > Number(yHasta)) { setLockMsg('Rango inválido: Desde > Hasta.'); return; }
  if (!state.collection.length) { setLockMsg('No existen series en la colección.'); return; }

  const desde = yDesde + '-01';
  const hasta = yHasta + '-12';

  // preparar payload (todas las series de la colección)
  const items = state.collection.map(it => ({
    token: it.token,
    frecuencia: it.frecuencia,
    unidad: it.unidad
  }));
  const exportUrl = restApiUrl('export-collection');

  try {
    submitDownloadRequest(exportUrl, {
      items,
      desde,
      hasta,
      with_meta: withMeta,
      format: fmt
    });
    setLockMsg(null);
    closeDownloadPanel();
  } catch (e) {
    setLockMsg(`Error descarga: ${e.message}`);
  }
}

/* ---------------- Menus (Cuadro ?) ---------------- */

function closeActiveMenu() {
  if (typeof activeMenuCleanup === 'function') activeMenuCleanup();
  activeMenuCleanup = null;
}

function toggleMenu(btnId, menuId) {
  const menu = el(menuId);
  const btn = el(btnId);
  if (!menu || !btn) return;

  const visible = menu.style.display !== 'none';
  if (visible) {
    closeActiveMenu();
    return;
  }

  closeActiveMenu();
  menu.style.display = 'block';
  btn.classList.add('menu-open');
  if (menuId === 'menuCuadro') {
    const rb = el('btnTodo');
    if (rb) rb.checked = false;
  }

  const onDoc = (ev) => {
    if (!menu.contains(ev.target) && !btn.contains(ev.target)) {
      closeActiveMenu();
    }
  };
  const onKey = (ev) => {
    if (ev.key === 'Escape') closeActiveMenu();
  };
  activeMenuCleanup = () => {
    menu.style.display = 'none';
    btn.classList.remove('menu-open');
    document.removeEventListener('pointerdown', onDoc, true);
    document.removeEventListener('keydown', onKey, true);
  };
  document.addEventListener('pointerdown', onDoc, true);
  document.addEventListener('keydown', onKey, true);
}

async function doExportCuadro(fmt) {
  if (!state.activeGrupo || !state.freq || !state.unit) {
    setLockMsg('Seleccione frecuencia y unidad para exportar el cuadro.');
    return;
  }
  const parsed = readRangeFromInputs();
  if (parsed && parsed.desde <= parsed.hasta) {
    state.range.desde = parsed.desde;
    state.range.hasta = parsed.hasta;
    state.rangeApplied = true;
    if (state.freq) state.rangeByFreq[state.freq] = { desde: state.range.desde, hasta: state.range.hasta };
  }
  const desde = state.range.desde;
  const hasta = state.range.hasta;
  if (!desde || !hasta) {
    setLockMsg('Defina un rango válido para exportar.');
    return;
  }
  try {
    const exportUrl = restApiUrl('export-cuadro');
    const payload = {
      id_grupo: state.activeGrupo,
      frecuencia: state.freq,
      unidad: state.unit,
      desde,
      hasta,
      format: fmt
    };
    submitDownloadRequest(exportUrl, payload);
    setLockMsg(null);
  } catch (e) {
    setLockMsg(`Error descarga: ${e.message}`);
  }
}

/* ---------------- Init ---------------- */

async function init() {
  initInstantTooltips();
  promoteInstantTooltips(document);
  syncAddToCartButton();
  if (perf.enabled) {
    perf.t0 = performance.now();
    perfMark('init');
  }
  applyHighchartsLang();
  const inlineMsg = el('inlineMsg');
  if (inlineMsg && inlineMsg.parentElement !== document.body) {
    document.body.appendChild(inlineMsg);
  }
  // Drawer controls
  el('btnDrawer').addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    toggleDrawer();
  });
  const btnDrawerClose = el('btnDrawerClose');
  if (btnDrawerClose) {
    btnDrawerClose.addEventListener('pointerdown', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      closeDrawer();
    });
  }
  el('drawerBackdrop').addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    closeDrawer();
  });

  // Tree
  try {
    const tree = await getJson(restApiUrl('tree'));
    state.treeRaw = tree;
    state.treeBuilt = buildTreeFromFlat(tree);
    renderTree(state.treeBuilt);
    if (perf.enabled) perfMark('tree loaded', { nodes: state.treeRaw.length });
    try {
      await selectCuadro(35);
    } catch (e) {
      // noop: cuadro por defecto no disponible
    }
  } catch (e) {
    setLockMsg(`Error índice: ${e.message}`);
  }

  const treeFilterEl = el('treeFilter');
  if (treeFilterEl) {
    updateSearchInputUi(treeFilterEl.value);
    treeFilterEl.addEventListener('input', (ev) => {
      const v = normalizeSearchInput(ev.target.value, ev.target);
      treeFilterTouched = true;
      if (treeFilterTimer) clearTimeout(treeFilterTimer);
      treeFilterTimer = setTimeout(() => {
        if (drawerTab === 'serie') searchSeries(v);
        else applyTreeFilter(v);
      }, 160);
    });
  }
  const treeFilterClear = el('treeFilterClear');
  if (treeFilterClear && treeFilterEl) {
    treeFilterClear.addEventListener('click', () => {
      treeFilterEl.value = '';
      updateSearchInputUi('');
      setSearchLimitNotice('');
      if (treeFilterTimer) clearTimeout(treeFilterTimer);
      if (drawerTab === 'serie') {
        searchSeries('');
      } else {
        treeFilterTouched = false;
        applyTreeFilter('');
      }
      treeFilterEl.focus();
    });
  }

  const tabCuadro = el('tabCuadro');
  const tabSerie = el('tabSerie');
  if (tabCuadro) tabCuadro.addEventListener('click', () => setDrawerTab('cuadro'));
  if (tabSerie) tabSerie.addEventListener('click', () => setDrawerTab('serie'));
  setDrawerTab('cuadro');

  const seriesResults = el('seriesResults');
  if (seriesResults) {
    seriesResults.addEventListener('click', (ev) => {
      const t = ev.target;
      const item = t && t.closest ? t.closest('.series-item') : null;
      if (!item) return;
      const action = t?.dataset?.action || (t.closest('[data-action]')?.dataset?.action);
      if (!action) return;
      ev.preventDefault();
      const data = {
        token: item.getAttribute('data-token') || '',
        frecuencia: item.getAttribute('data-freq') || '',
        unidad: item.getAttribute('data-unit') || '',
        id_grupo: Number(item.getAttribute('data-grupo') || 0),
        cod_grupo: item.getAttribute('data-cod') || '',
        nom_grupo: item.getAttribute('data-nom') || '',
        ruta: item.getAttribute('data-ruta') || '',
        nombre_serie: item.getAttribute('data-label') || '',
      };
      if (action === 'open') {
        if (data.id_grupo) selectCuadro(data.id_grupo);
        if (data.token) pendingFocusToken = data.token;
        closeDrawer();
        return;
      }
      if (action === 'add') {
        addSeriesFromSearch(data);
      }
    });
  }

  // Cerrar metadata al hacer clic fuera
  document.addEventListener('click', (ev) => {
    const pop = el('metaPopover');
    const popFs = el('metaPopoverFs');
    const popOpen = (pop && pop.style.display !== 'none') || (popFs && popFs.style.display !== 'none');
    if (!popOpen) return;
    const t = ev.target;
    if (pop && pop.contains(t)) return;
    if (popFs && popFs.contains(t)) return;
    if (t && t.closest && t.closest('button.info')) return;
    hideMetaPopover();
  }, true);

  // Cerrar alertas al hacer clic en cualquier parte de la pantalla
  document.addEventListener('click', () => {
    if (!state.lockMsg) return;
    if (state.lockMsgAt && (Date.now() - state.lockMsgAt) < 300) return;
    setLockMsg(null);
  }, true);

  // Delegación de eventos en grid (mejor performance en tablas grandes)
  const gridEl = el('grid');
  if (gridEl && !gridEventsBound) {
    gridEl.addEventListener('change', (ev) => {
      const t = ev.target;
      if (!t) return;
      if (t.id === 'chkAll') {
        const candidates = Array.from(gridEl.querySelectorAll('input[type="checkbox"][data-token]'));
        candidates.forEach(c => {
          if (c.disabled) return;
          c.checked = t.checked;
          const token = c.getAttribute('data-token');
          if (!token) return;
          if (c.checked) state.marked.add(token);
          else state.marked.delete(token);
        });
        if (gridUpdateAllState) gridUpdateAllState();
        syncAddToCartButton();
        return;
      }
      if (t.matches && t.matches('input[type="checkbox"][data-token]')) {
        const token = t.getAttribute('data-token');
        if (!token) return;
        if (t.checked) state.marked.add(token);
        else state.marked.delete(token);
        if (gridUpdateAllState) gridUpdateAllState();
        syncAddToCartButton();
      }
    });
    gridEl.addEventListener('click', (ev) => {
      const infoBtn = ev.target.closest ? ev.target.closest('button[data-info]') : null;
      if (infoBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        const token = infoBtn.getAttribute('data-info');
        if (token) openMeta(token, infoBtn);
        return;
      }
      const chartBtn = ev.target.closest ? ev.target.closest('button[data-chart]') : null;
      if (chartBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        const token = chartBtn.getAttribute('data-chart');
        if (token) openSeriesChartModal(token);
      }
    });
    gridEventsBound = true;
  }

  // Frecuencia change: NO borrar colección; recargar el cuadro completo usando todo el rango disponible de la nueva frecuencia.
  el('selFreq').addEventListener('change', async () => {
    state.freq = el('selFreq').value;
    setText('freqVal', state.freq || '');
    setText('unitVal', '-');
    const nextRange = getRangeForCurrentFreq();
    state.range.desde = nextRange?.minYm || null;
    state.range.hasta = nextRange?.maxYm || null;
    normalizeRangeForFreq();
    applyCalendarMode();
    updatePeriodoVal();
    state.rangeApplied = false;

    // reset marcados
    state.marked = new Set();
    syncAddToCartButton();

    // aplicar policy unidad y cargar grid (autoselección si única)
    await applyUnitPolicyAndLoad();

    // refrescar estados en grid
    updateCollectionUI();
  });

  // Unidad change
  el('selUnit').addEventListener('change', async () => {
    const prevDesde = state.range.desde;
    const prevHasta = state.range.hasta;
    const selectedUnit = el('selUnit').value;
    const validUnits = getUnitsForCurrentFreq();
    if (!isValidUnitForFreq(selectedUnit, state.freq)) {
      if (validUnits.length) {
        state.unit = validUnits[0];
        el('selUnit').value = state.unit;
        setText('unitVal', state.unit || '');
        setLockMsg('Unidad ajustada automáticamente para la frecuencia seleccionada.');
      } else {
        state.unit = '';
        el('selUnit').value = '';
        setText('unitVal', '');
        setLockMsg('No existen unidades disponibles para la frecuencia seleccionada.');
      }
      el('gridEmpty').textContent = 'Selecciona una unidad.';
      el('gridEmpty').style.display = 'flex';
      el('gridScroll').style.display = 'none';
      return;
    }

    state.unit = selectedUnit;
    setText('unitVal', state.unit || '-');

    state.marked = new Set();
    syncAddToCartButton();

    if (!state.unit) {
      setLockMsg('Seleccione unidad para visualizar el cuadro.');
      el('gridEmpty').textContent = 'Selecciona una unidad.';
      el('gridEmpty').style.display = 'flex';
      el('gridScroll').style.display = 'none';
      return;
    }

    setLockMsg(null);
    if (!adaptRangeByYears(prevDesde, prevHasta)) normalizeRangeForFreq();
    await loadGrid();
    updateCollectionUI();
  });

  // Cuadro menu
  el('btnCuadro').addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    toggleMenu('btnCuadro','menuCuadro');
  });
  const btnCollRange = el('btnCollRange');
  if (btnCollRange) {
    btnCollRange.addEventListener('pointerdown', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (!state.collection.length) { setLockMsg('No existen series en la colección.'); return; }
      const rb = el('btnCollTodo');
      if (rb) rb.checked = false;
      toggleMenu('btnCollRange','menuCollRange');
    });
  }
  const btnCollTodo = el('btnCollTodo');
  if (btnCollTodo) {
    btnCollTodo.addEventListener('click', () => {
      const full = state.collectionRangeFull;
      if (!full?.desde || !full?.hasta) return;
      const fromEl = el('collDesde');
      const toEl = el('collHasta');
      const minY = ymToYear(full.desde);
      const maxY = ymToYear(full.hasta);
      if (fromEl && minY) fromEl.value = String(minY);
      if (toEl && maxY) toEl.value = String(maxY);
    });
  }
  const btnCollAplicar = el('btnCollAplicar');
  if (btnCollAplicar) {
    btnCollAplicar.addEventListener('click', () => {
      const parsed = readCollectionRangeFromInputs();
      if (!parsed) { setLockMsg('Defina un rango válido.'); return; }
      applyCollectionRange(parsed);
      closeActiveMenu();
    });
  }
  // Exportar cuadro directo a Excel
  el('btnExportCuadro').addEventListener('click', async (ev) => {
    ev.preventDefault();
    await doExportCuadro('xlsx');
  });

  // Grid fullscreen
  const btnFs = el('btnGridFullscreen');
  if (btnFs) {
    setGridFullscreen(isGridFullscreen());
    btnFs.addEventListener('click', (ev) => {
      ev.preventDefault();
      setGridFullscreen(!isGridFullscreen());
    });
  }
  const btnSplit = el('btnPanelSplit');
  if (btnSplit) {
    setPanelSplit(isPanelSplit());
    btnSplit.addEventListener('click', (ev) => {
      ev.preventDefault();
      setPanelSplit(!isPanelSplit());
    });
  }
  const btnSortCuadro = el('btnSortCuadro');
  const btnSortFrecuencia = el('btnSortFrecuencia');
  const btnSortUnidad = el('btnSortUnidad');
  if (btnSortCuadro && btnSortFrecuencia && btnSortUnidad) {
    btnSortCuadro.addEventListener('click', () => {
      state.collectionSort = 'cuadro';
      updateCollectionUI();
    });
    btnSortFrecuencia.addEventListener('click', () => {
      state.collectionSort = 'frecuencia';
      updateCollectionUI();
    });
    btnSortUnidad.addEventListener('click', () => {
      state.collectionSort = 'unidad';
      updateCollectionUI();
    });
  }
  el('btnTodo').addEventListener('click', () => {
    const r = getRangeForCurrentFreq();
    if (!r?.minYm || !r?.maxYm) return;
    state.range.desde = r.minYm;
    state.range.hasta = r.maxYm;
    state.rangeApplied = true;
    if (state.freq) state.rangeByFreq[state.freq] = { desde: state.range.desde, hasta: state.range.hasta };
    applyCalendarMode();
    updatePeriodoVal();
  });
  el('btnAplicar').addEventListener('click', async () => {
    const parsed = readRangeFromInputs();
    if (!parsed) { setLockMsg('Defina un rango válido.'); return; }
    if (parsed.desde > parsed.hasta) { setLockMsg('Rango inválido: Desde > Hasta.'); return; }
    state.range.desde = parsed.desde;
    state.range.hasta = parsed.hasta;
    state.rangeApplied = true;
    if (state.freq) state.rangeByFreq[state.freq] = { desde: state.range.desde, hasta: state.range.hasta };
    closeActiveMenu();
    applyCalendarMode();
    updatePeriodoVal();

    if (state.unit) await loadGrid();
  });

  // Add to cart
  el('btnAddToCart').addEventListener('click', () => addMarkedToCollection());

  // Chart: habilitado pero sin render inicial hasta que el usuario active series
  el('chkChart').checked = true;
  el('chkChart').disabled = true;
  state.chartOn = true;

  // Collection actions
  el('btnClearSeries').addEventListener('click', clearCollection);
  el('btnDownloadSeries').addEventListener('click', openDownloadPanel);

  // download panel
  el('btnCloseDl').addEventListener('click', closeDownloadPanel);
  el('dlPanel').addEventListener('click', (ev) => { if (ev.target === el('dlPanel')) closeDownloadPanel(); });
  el('btnDoDownload').addEventListener('click', doDownloadCollection);

  // Meta modal close
  el('btnCloseModal').addEventListener('click', () => el('modal').style.display = 'none');
  el('modal').addEventListener('click', (ev) => { if (ev.target === el('modal')) el('modal').style.display = 'none'; });

  // Series chart modal
  el('btnCloseChart').addEventListener('click', closeSeriesChartModal);
  el('chartModal').addEventListener('click', (ev) => { if (ev.target === el('chartModal')) closeSeriesChartModal(); });
  el('btnApplyChart').addEventListener('click', (ev) => { ev.preventDefault(); loadSeriesChart(); });
  window.addEventListener('resize', onUnitIndentResize);

  // Start
  updateCollectionUI();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
















