const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, data) {
  const response = await fetch('api/' + path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}

function showError(error) {
  $('results').className = 'panel results-panel';
  $('results').innerHTML = `<div class="alert"><h2>Something went wrong</h2><p>${escapeHTML(error.message)}</p></div>`;
}

$('example').onclick = () => {
  $('intake').reset();
  $('symptoms').value = 'I want to find a primary care clinic';
  $('zip').value = '90012';
  $('insurance').value = 'uninsured';
};

$('intake').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  try {
    const result = await api('navigate', Object.fromEntries(new FormData($('intake'))));
    $('results').className = 'panel results-panel';
    if (result.urgent) {
      $('results').innerHTML = `<div class="alert"><h2>Possible emergency</h2><p>${escapeHTML(result.message)}</p><strong>${escapeHTML(result.notice)}</strong></div>`;
      return;
    }
    $('results').innerHTML = `<div class="panel-header"><div><div class="eyebrow">Next steps</div><h2>Care-navigation response</h2></div></div><p class="muted">${escapeHTML(result.message)}</p>` +
      `<div class="summary-grid"><div class="summary-card"><span>Status</span><strong>${result.questions.length ? 'Needs a few more details' : 'Ready for outreach'}</strong></div><div class="summary-card"><span>Insurance</span><strong>${escapeHTML(($('insurance').value || 'unspecified').replace(/^./, c => c.toUpperCase()))}</strong></div><div class="summary-card"><span>ZIP code</span><strong>${escapeHTML(result.preferences.zip || 'Not provided')}</strong></div><div class="summary-card"><span>Resources</span><strong>${result.resources.length} official starting point${result.resources.length === 1 ? '' : 's'}</strong></div></div>` +
      `<div class="section-stack">` +
      `<section class="section-card"><h3>Recommended next step</h3><p><strong>Care level:</strong> ${escapeHTML(result.recommendations.care_level)}</p><p class="small">${escapeHTML(result.recommendations.summary)}</p></section>` +
      `<section class="section-card"><h3>Recommended doctor type</h3><ul>${result.recommendations.doctor_types.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul></section>` +
      `<section class="section-card"><h3>General recommendations</h3>` +
      (result.recommendations.matched_topics.length ? `<p class="small"><strong>Matched topics:</strong> ${escapeHTML(result.recommendations.matched_topics.join(', '))}</p>` : '') +
      (result.recommendations.possible_causes.length ? `<h4>Possible causes to discuss</h4><ul>${result.recommendations.possible_causes.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul>` : '') +
      (result.recommendations.self_care.length ? `<h4>General self-care and monitoring</h4><ul>${result.recommendations.self_care.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul>` : '') +
      (result.recommendations.care_options.length ? `<h4>Care settings that may fit</h4><ul>${result.recommendations.care_options.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul>` : '') +
      `</section>` +
      `<section class="section-card"><h3>Nearby care options</h3><p class="small">${escapeHTML(result.providers.summary)}</p><div class="resource-grid">${result.providers.cards.map(card => `<article class="resource"><div class="tag">${escapeHTML(card.source || 'Clinic directory')}</div><a href="${escapeHTML(card.website)}" target="_blank" rel="noopener noreferrer">${escapeHTML(card.title)} ↗</a><p>${escapeHTML(card.address)}</p><ul>${card.details.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul></article>`).join('')}</div></section>` +
      `<section class="section-card"><h3>Insurance and affordability</h3><p class="small">${escapeHTML(result.affordability.summary)}</p><ul>${result.affordability.items.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul></section>` +
      `<section class="section-card"><h3>Free local resources</h3><p class="small">${escapeHTML(result.free_resources.summary)}</p><ul>${result.free_resources.items.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul></section>` +
      (result.questions.length ? `<section class="section-card"><h3>Helpful follow-up questions</h3>${result.questions.map(q => `<div class="question">${escapeHTML(q.text)}</div>`).join('')}<p class="small">Update the form with these preferences and submit again. These links are still general, not personalized clinic matches.</p></section>` : '') +
      `<section class="section-card"><h3>Next steps</h3><ol>${result.steps.map(step => `<li>${escapeHTML(step)}</li>`).join('')}</ol></section>` +
      `<section class="section-card"><h3>Official resources to open next</h3><div class="resource-grid">${result.resources.map(r => `<article class="resource"><div class="tag">${escapeHTML(r.kind)}</div><a href="${escapeHTML(r.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(r.name)} ↗</a><p>${escapeHTML(r.description)}</p></article>`).join('')}</div></section></div>`;
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
});
