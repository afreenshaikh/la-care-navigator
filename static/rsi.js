const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, data) {
  const response = await fetch('api/' + path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}

function metric(label, value) {
  return `<div class="summary-card"><span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong></div>`;
}

function testList(title, score) {
  return `<section class="section-card"><h3>${escapeHTML(title)}</h3>${score.results.map(r => `<div class="test-row"><span>${escapeHTML(r.name)}${r.missing?.length ? ' · missing: ' + escapeHTML(r.missing.join(', ')) : ''}${r.repeated?.length ? ' · repeated: ' + escapeHTML(r.repeated.join(', ')) : ''}</span><strong>${r.passed ? 'PASS' : 'FAIL'}</strong></div>`).join('')}</section>`;
}

function renderCandidate(patch) {
  if (!patch) {
    $('candidate').innerHTML = '<p class="muted">No proposed change yet.</p>';
    return;
  }
  if (patch.done) {
    $('candidate').innerHTML = `<div class="section-card"><h3>Proposer status</h3><p>${escapeHTML(patch.message)}</p></div>`;
    return;
  }
  $('candidate').innerHTML = `<div class="section-card"><h3>Proposed patch</h3><p>${escapeHTML(patch.reason)}</p><pre>${escapeHTML(patch.change.key)}: false → true</pre><p class="small">Development: ${patch.development_before.passed}/${patch.development_before.total} → ${patch.development_after.passed}/${patch.development_after.total}<br>Holdout: ${patch.holdout_before.passed}/${patch.holdout_before.total} → ${patch.holdout_after.passed}/${patch.holdout_after.total}<br>Safety checks: ${patch.safety.passed}/${patch.safety.total}</p><div class="button-row admin-row"><button id="approve" class="primary" type="button" ${patch.eligible ? '' : 'disabled'}>Approve</button><button id="reject" class="secondary" type="button">Reject</button></div></div>`;
  $('approve').onclick = async () => { await api('approve', {}); await refresh(); };
  $('reject').onclick = async () => { await api('reject', {}); await refresh(); };
}

async function refresh() {
  try {
    const state = await api('state');
    $('metrics').innerHTML = [
      metric('Version', state.version),
      metric('Development', `${state.development.passed}/${state.development.total}`),
      metric('Holdout', `${state.holdout.passed}/${state.holdout.total}`),
      metric('Safety', `${state.safety.passed}/${state.safety.total}`),
    ].join('');
    $('policy').textContent = JSON.stringify(state.policy, null, 2);
    $('evaluations').innerHTML = testList('Development suite', state.development) + testList('Holdout suite', state.holdout) + testList('Safety regressions', state.safety);
    $('history').innerHTML = state.history.length ? state.history.map(h => `<div class="section-card"><h3>Version ${escapeHTML(h.version)}</h3><p>${escapeHTML(h.reason)}</p><p class="small">Changed: ${escapeHTML(h.change.key)} · development ${escapeHTML(h.development_passed)} · holdout ${escapeHTML(h.holdout_passed)}</p></div>`).join('') : '<p class="muted">No approved changes yet.</p>';
    renderCandidate(state.pending);
  } catch (error) {
    $('candidate').innerHTML = `<div class="alert"><h2>Something went wrong</h2><p>${escapeHTML(error.message)}</p></div>`;
  }
}

$('propose').onclick = async () => { try { await api('propose', {}); await refresh(); } catch (error) { $('candidate').innerHTML = `<div class="alert"><h2>Something went wrong</h2><p>${escapeHTML(error.message)}</p></div>`; } };
$('refresh').onclick = () => refresh();
refresh();
