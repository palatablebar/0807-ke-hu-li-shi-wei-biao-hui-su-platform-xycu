import {request, element} from './client.js';
import {badge} from './view.js';

const form = document.querySelector('#supplement');
const file = document.querySelector('#supplement-file');
const profile = document.querySelector('#supplement-profile');
const filename = document.querySelector('#supplement-name');
const publish = document.querySelector('#publish');
const board = document.querySelector('#trial');
const state = document.querySelector('#release-state');
const versions = document.querySelector('#releases');
let outcome = null, busy = false;

function say(text, failure = false) {
  state.textContent = text;
  state.dataset.failure = String(failure);
}

function source(expected) {
  const data = new FormData();
  if (file.files.length) data.append('file', file.files[0]);
  else data.append('sample', profile.value);
  if (expected) data.append('expected', expected);
  return data;
}

const spans = list => list.length ? list.map(([start, end]) => `[${start},${end})`).join(' ∪ ') : '—';

function caseBlock(row) {
  const box = element('div', undefined, {class: 'case-block'});
  const head = element('header');
  head.append(element('strong', `客户 ${row.case}`), badge(row.status));
  box.append(head);
  const cov = row.coverage;
  box.append(element('p', `覆盖 ${spans(cov.before)} → ${spans(cov.after)} · 新增 ${spans(cov.added)}`, {class: 'cov'}));
  if (row.points.length) {
    const line = element('p', undefined, {class: 'points'});
    for (const point of row.points) {
      const mark = `${point.before ? '✓' : '✗'}→${point.after ? '✓' : '✗'}`;
      const delta = !point.after ? 'open' : (!point.before ? 'gained' : 'same');
      line.append(element('span', `${point.record}@${point.day} ${mark}`, {class: 'point', 'data-delta': delta, title: point.origin === 'baseline' ? '基线交易' : '补录交易'}));
    }
    box.append(line);
  }
  const issues = row.issues;
  const parts = [];
  if (issues.gap.length) parts.push(`断档 ${issues.gap.join('、')}`);
  if (issues.overlap.length) parts.push(`重叠 ${issues.overlap.join('、')}`);
  if (issues.unlinked.length) parts.push(`未关联交易 ${issues.unlinked.join('、')}`);
  if (parts.length) box.append(element('p', parts.join(' · '), {class: 'warn'}));
  return box;
}

function renderTrial(data) {
  board.replaceChildren();
  const summary = data.summary;
  board.append(element('p',
    `基线 ${data.baseline ? '#' + data.baseline.seq : '无'} · 采信 ${data.intake.accepted} 行 · 隔离 ${data.intake.rejected} 行 · 回放 ${summary.replays} 行 · 未解决交易 ${summary.unresolved}`,
    {class: 'trial-meta'}));
  if (data.conflicts.length) {
    board.append(element('p', `与基线冲突已隔离:${data.conflicts.map(item => item.record).join('、')}`, {class: 'warn'}));
  }
  for (const row of data.cases) board.append(caseBlock(row));
  if (!data.cases.length) board.append(element('p', '补录内容没有可试算的记录'));
}

async function trial() {
  if (busy) return;
  busy = true;
  publish.disabled = true;
  say('试算中…');
  try {
    outcome = await request('/api/releases/trial', {method: 'POST', body: source()});
    renderTrial(outcome);
    if (outcome.existing) say(`内容与版本 #${outcome.existing.seq} 相同,无需新增`);
    else if (!outcome.cases.length) say('没有可发布的记录', true);
    else {
      publish.disabled = false;
      say(outcome.summary.publishable ? '试算通过,可新建发布版本' : '存在断档、重叠或未关联交易,发布将保持待复核');
    }
  } catch (error) {
    outcome = null;
    board.replaceChildren();
    say(error.message, true);
  } finally {
    busy = false;
  }
}

async function loadReleases() {
  const data = await request('/api/releases');
  versions.replaceChildren();
  for (const item of data.items) {
    const li = element('li');
    li.append(
      element('button', `#${item.seq} · ${item.id.slice(0, 8)}`, {type: 'button', 'data-release': item.id}),
      badge(item.status),
      element('a', '证据', {href: `/api/releases/${item.id}/evidence`}));
    versions.append(li);
  }
  if (!data.items.length) versions.append(element('li', '尚无发布版本'));
}

export function initRelease() {
  file.addEventListener('change', () => {
    filename.textContent = file.files[0]?.name || '';
    trial();
  });
  profile.addEventListener('change', () => {
    file.value = '';
    filename.textContent = '';
    trial();
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!outcome || busy) return;
    busy = true;
    publish.disabled = true;
    say('发布中…');
    (async () => {
      let stale = false;
      try {
        const release = await request('/api/releases', {method: 'POST', body: source(outcome.manifest.release_id)});
        outcome = null;
        renderTrial(release.report);
        say(release.status === 'PUBLISHED'
          ? `版本 #${release.seq} 已发布,次日重算将使用`
          : `版本 #${release.seq} 保持待复核,记录键已列出`, release.status !== 'PUBLISHED');
        await loadReleases();
      } catch (error) {
        say(error.message, true);
        stale = error.code === 'TRIAL_STALE';
        if (!stale) publish.disabled = !outcome;
      } finally {
        busy = false;
      }
      if (stale) await trial();
    })();
  });
  versions.addEventListener('click', event => {
    const button = event.target.closest('[data-release]');
    if (button) request(`/api/releases/${button.dataset.release}`)
      .then(release => {
        renderTrial(release.report);
        say(`查看版本 #${release.seq} · ${release.status} · 按原时点复现`);
      })
      .catch(error => say(error.message, true));
  });
  loadReleases().then(trial).catch(error => say(error.message, true));
}
