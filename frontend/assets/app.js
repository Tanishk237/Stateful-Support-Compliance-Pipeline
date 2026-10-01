import { resetGraph, graphEvent, graphError, restoreGraph } from './graph.js';
import { setupSpeech } from './speech.js';

const $ = id => document.getElementById(id);
const input = $('email');
const scenarios = {
  verified: ['Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge.', 'A complete complaint that matches the demo billing record.'],
  clarify: ['Hello, my name is Alice Johnson. I was billed $120 but expected $100 for a billing issue.', 'The account number is missing. Answer with ACC1023 when asked.'],
  privacy: ['Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100. My SSN is 123-45-6789.', 'Synthetic sensitive data. Watch compliance stop the request before extraction.'],
  review: ['Hello, my name is Morgan Reed. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge.', 'The customer name does not match the demo account. Expect a billing review.'],
};
const labels = { customer_name: 'Customer name', account_id: 'Account ID', claimed_amount: 'Billed amount', expected_amount: 'Expected amount', issue_type: 'Issue type' };
const outcomes = {
  respond: ['Response ready', 'The complaint matches the demo billing record.', 'success'],
  clarify: ['A little more context', 'The workflow is paused. Add the missing details to continue.', 'warning'],
  billing_review: ['Over to the billing team', 'A review ticket was created with the verification details.', 'warning'],
  compliance_escalation: ['Privacy needs a closer look', 'Sensitive data was flagged. Extraction was not run.', 'danger'],
  pending: ['An unfinished request', 'This is the last saved checkpoint. Start a new run to try again.', 'warning'],
};
let state = null;
let busy = false;
let listening = false;
let activeRequest = '';

function text(parent, tag, value, className = '') {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
  return element;
}
function announce(message) { $('announcement').textContent = message; }
function showError(message = '') {
  $('request-error').textContent = message;
  $('request-error').hidden = !message;
}
function updateCount() { $('character-count').textContent = `${input.value.length.toLocaleString()} / 10,000`; }
const speech = setupSpeech({ input, onChange: updateCount, onListening(value) { listening = value; updateControls(); } });

function updateControls() {
  document.querySelectorAll('#complaint-form button:not(#speech-toggle), #restore-form button, #clarification-form button, .scenario, #reset-demo').forEach(button => { button.disabled = busy || listening; });
  input.disabled = busy;
  speech.setDisabled(busy);
  $('results').setAttribute('aria-busy', String(busy));
  $('run-button').querySelector('span').textContent = busy ? 'Workflow running…' : 'Run workflow';
}
input.addEventListener('input', updateCount);
updateCount();

function selectScenario(name) {
  input.value = scenarios[name][0];
  $('scenario-hint').textContent = scenarios[name][1];
  document.querySelectorAll('[data-scenario]').forEach(button => {
    const selected = button.dataset.scenario === name;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  showError();
  updateCount();
}
document.querySelectorAll('[data-scenario]').forEach(button => button.addEventListener('click', () => selectScenario(button.dataset.scenario)));
$('reset-demo').addEventListener('click', () => {
  input.value = '';
  input.focus();
  $('scenario-hint').textContent = 'Write or dictate a sample billing issue. The demo record below is available to try.';
  document.querySelectorAll('[data-scenario]').forEach(button => { button.classList.remove('selected'); button.setAttribute('aria-pressed', 'false'); });
  updateCount();
  showError();
});

function rememberRequest(id) {
  activeRequest = id;
  $('request-id-input').value = id;
  const url = new URL(window.location.href);
  url.searchParams.set('request', id);
  history.replaceState(null, '', url);
}

async function readError(response) {
  const payload = await response.json().catch(() => ({}));
  return typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status}). Please check the input and retry.`;
}

async function run(url, payload, resuming = false) {
  if (busy || listening) return;
  busy = true;
  updateControls();
  showError();
  resetGraph(resuming);
  $('result-empty').hidden = true;
  $('result-content').hidden = true;
  $('result-loading').hidden = false;
  $('result-label').textContent = 'Processing';
  if (!resuming) {
    state = null;
    activeRequest = '';
    const currentURL = new URL(location.href);
    currentURL.searchParams.delete('request');
    history.replaceState(null, '', currentURL);
  }
  const started = performance.now();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);
  let reader;
  let completed = false;
  try {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(payload), signal: controller.signal });
    if (!response.ok) throw new Error(await readError(response));
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n');
        if (!data) continue;
        const event = JSON.parse(data);
        if (event.type === 'error') throw new Error(event.message);
        if (event.type === 'request_started') rememberRequest(event.request_id);
        graphEvent(event);
        if (event.type === 'complete') {
          state = event.state;
          completed = true;
          renderState(state, `${((performance.now() - started) / 1000).toFixed(2)} s · round trip`);
          announce(state.route === 'clarify' ? 'Your answer is needed to continue.' : 'Workflow complete. Results and activity are ready.');
        }
      }
    }
    if (!completed) throw new Error('The live connection ended before completion.');
  } catch (error) {
    graphError();
    const message = error.name === 'AbortError' ? 'This run took too long to respond.' : error.message;
    showError(`${message}${activeRequest ? ` Request ID: ${activeRequest}. Use “Reopen a saved request” to check its saved state.` : ''}`);
    $('result-label').textContent = 'Run interrupted';
    if (state) renderState(state, 'Previous saved result');
    else $('result-empty').hidden = false;
  } finally {
    clearTimeout(timeout);
    await reader?.cancel().catch(() => {});
    $('result-loading').hidden = true;
    busy = false;
    updateControls();
  }
}

$('complaint-form').addEventListener('submit', event => {
  event.preventDefault();
  if (!input.value.trim()) { showError('Please type or dictate a billing complaint first.'); return; }
  run('/complaints/stream', { email: input.value });
});
$('clarification-form').addEventListener('submit', event => {
  event.preventDefault();
  if (!state) return;
  const answers = Object.fromEntries(new FormData(event.currentTarget));
  run(`/complaints/${encodeURIComponent(state.request_id)}/clarification/stream`, { answers }, true);
});

function showTab(name, focus = false) {
  document.querySelectorAll('[data-tab]').forEach(button => {
    const selected = button.dataset.tab === name;
    button.setAttribute('aria-selected', String(selected));
    button.tabIndex = selected ? 0 : -1;
    $(`panel-${button.dataset.tab}`).hidden = !selected;
    if (selected && focus) button.focus();
  });
}
document.querySelectorAll('[data-tab]').forEach((button, index, buttons) => {
  button.addEventListener('click', () => showTab(button.dataset.tab));
  button.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % buttons.length;
    if (event.key === 'ArrowLeft') next = (index + buttons.length - 1) % buttons.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = buttons.length - 1;
    if (next !== undefined) { event.preventDefault(); showTab(buttons[next].dataset.tab, true); }
  });
});

function renderState(saved, duration = 'Reopened from SQLite') {
  $('result-empty').hidden = true;
  $('result-loading').hidden = true;
  $('result-content').hidden = false;
  const [title, description, tone] = outcomes[saved.route] || outcomes.pending;
  $('outcome-title').textContent = title;
  $('outcome-description').textContent = description;
  $('outcome-banner').dataset.tone = tone;
  $('outcome-banner').querySelector('img').src = `/assets/${saved.route === 'respond' ? 'check' : saved.route === 'compliance_escalation' ? 'shield-check' : 'route'}.svg`;
  $('result-label').textContent = saved.route.replaceAll('_', ' ');
  $('request-id').textContent = saved.request_id;
  $('run-duration').textContent = duration;
  $('final-output').textContent = saved.route === 'clarify' ? '' : saved.final_output || 'No final output has been generated.';
  $('output-note').textContent = saved.escalation_ticket.ticket_id
    ? `Ticket ${saved.escalation_ticket.ticket_id} · ${saved.escalation_ticket.department} · ${saved.escalation_ticket.priority} priority. Stored locally; not sent to an external helpdesk.`
    : 'This is a demonstration. Responses are drafts; no refund or account change is performed.';
  renderClarification(saved);
  $('extracted-fields').replaceChildren();
  for (const [key, label] of Object.entries(labels)) {
    const row = text($('extracted-fields'), 'div', '');
    text(row, 'dt', label);
    const value = saved.extracted_information[key];
    text(row, 'dd', value === null || value === '' ? 'Not extracted' : typeof value === 'number' ? `$${value.toFixed(2)}` : value.replaceAll('_', ' '));
  }
  const provenance = $('extraction-provenance');
  provenance.replaceChildren();
  text(provenance, 'p', saved.extraction_source === 'pending' ? 'Extraction was not run.' : `Source: ${saved.extraction_source.startsWith('llm') ? 'LLM' : 'Deterministic fallback'}`);
  if (saved.extraction_prompt_version) text(provenance, 'p', `Prompt version: ${saved.extraction_prompt_version}`);
  if (saved.extraction_source !== 'pending') {
    const detail = text(provenance, 'details', '');
    text(detail, 'summary', 'Extraction details');
    text(detail, 'p', saved.extraction_source);
  }
  const compliance = saved.compliance_result;
  $('compliance-summary').textContent = saved.compliance_status === 'pending' ? 'Not run yet.' : `${compliance.is_safe ? 'Passed' : 'Flagged'} · Risk: ${compliance.risk_level}. ${compliance.pii_found.length ? `Detected: ${compliance.pii_found.join(', ')}.` : 'No supported sensitive-data patterns detected.'}`;
  $('redacted-email').textContent = saved.redacted_email || 'No redacted input available.';
  renderVerification(saved);
  $('execution-history').replaceChildren();
  for (const event of saved.execution_history) {
    const row = text($('execution-history'), 'li', '');
    const heading = text(row, 'div', '', 'event-heading');
    text(heading, 'strong', event.step.replaceAll('_', ' '));
    text(heading, 'span', event.status);
    if (event.details) text(row, 'p', event.details);
  }
  showTab('output');
}

function renderClarification(saved) {
  $('clarification').hidden = saved.route !== 'clarify';
  $('clarification-question').textContent = saved.clarification_question;
  $('clarification-fields').replaceChildren();
  if (saved.route !== 'clarify') return;
  for (const field of saved.missing_fields) {
    const wrapper = text($('clarification-fields'), 'div', '');
    const label = text(wrapper, 'label', labels[field] || field);
    label.htmlFor = `answer-${field}`;
    const answer = document.createElement('input');
    answer.name = field;
    answer.id = label.htmlFor;
    answer.required = true;
    answer.autocomplete = 'off';
    if (field.endsWith('_amount')) { answer.type = 'number'; answer.min = '0'; answer.step = '0.01'; }
    else answer.maxLength = 200;
    if (field === 'account_id') answer.placeholder = 'Demo account: ACC1023';
    wrapper.append(answer);
  }
}

function renderVerification(saved) {
  const target = $('business-checks');
  target.replaceChildren();
  if (saved.verification_status === 'pending') { text(target, 'p', 'Not run. Verification follows successful privacy and validation checks.', 'small muted'); return; }
  const checks = { account_found: 'Account exists', identity_match: 'Customer name matches', claimed_amount_match: 'Billed amount matches', expected_amount_match: 'Expected amount matches', account_active: 'Account is active', discrepancy_match: 'Discrepancy matches' };
  for (const [key, label] of Object.entries(checks)) {
    const row = text(target, 'div', '', 'check-row');
    text(row, 'span', label);
    text(row, 'span', saved.business_verification[key] ? 'Passed' : 'Failed', `check-value${saved.business_verification[key] ? '' : ' failed'}`);
  }
  for (const [key, label] of [['calculated_discrepancy', 'Calculated discrepancy'], ['recorded_discrepancy', 'Recorded discrepancy']]) {
    const row = text(target, 'div', '', 'check-row');
    text(row, 'span', label);
    const amount = saved.business_verification[key];
    text(row, 'span', amount === null ? 'Unavailable' : `$${amount.toFixed(2)}`);
  }
  const codes = text(target, 'div', '', 'reason-codes');
  saved.business_verification.reason_codes.forEach(code => text(codes, 'span', code));
}

async function restore(id) {
  if (busy || listening) return;
  busy = true;
  updateControls();
  showError();
  try {
    const response = await fetch(`/complaints/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error(await readError(response));
    state = await response.json();
    input.value = state.raw_email;
    $('scenario-hint').textContent = 'Saved request reopened. Inspect its results, or edit the text to start a new run.';
    document.querySelectorAll('[data-scenario]').forEach(button => { button.classList.remove('selected'); button.setAttribute('aria-pressed', 'false'); });
    updateCount();
    rememberRequest(state.request_id);
    restoreGraph(state);
    renderState(state);
    announce('Saved request restored, including its workflow history.');
  } catch (error) { showError(error.message); }
  finally { busy = false; updateControls(); }
}
$('restore-form').addEventListener('submit', event => { event.preventDefault(); restore($('request-id-input').value.trim()); });
$('copy-output').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(state.final_output || state.clarification_question); announce('Output copied.'); }
  catch { announce('Clipboard access is unavailable. Select the output text to copy it.'); }
});
$('download-state').addEventListener('click', () => {
  if (!state) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `${state.request_id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  announce('Workflow state downloaded. It includes the original demo input.');
});

// Presentation preferences never store complaint data.
const darkQuery = matchMedia('(prefers-color-scheme: dark)');
const isDark = () => document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : darkQuery.matches;
function themeLabel() {
  $('theme-toggle').setAttribute('aria-label', `Switch to ${isDark() ? 'light' : 'dark'} theme`);
  $('theme-toggle').querySelector('img').src = `/assets/${isDark() ? 'sun' : 'moon'}.svg`;
}
$('theme-toggle').addEventListener('click', () => {
  const theme = isDark() ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('resolve-theme', theme); } catch { /* Optional preference. */ }
  themeLabel();
});
darkQuery.addEventListener('change', themeLabel);
themeLabel();
$('motion-toggle').addEventListener('click', () => {
  const paused = $('motion-toggle').getAttribute('aria-pressed') !== 'true';
  $('motion-toggle').setAttribute('aria-pressed', String(paused));
  document.documentElement.dataset.motion = paused ? 'paused' : 'playing';
  $('motion-toggle').querySelector('span').textContent = paused ? 'Resume motion' : 'Pause motion';
  $('motion-toggle').querySelector('img').src = `/assets/${paused ? 'player-play' : 'player-pause'}.svg`;
});
if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.remove('waiting'); observer.unobserve(entry.target); }
  }), { threshold: 0.08 });
  document.querySelectorAll('.reveal').forEach(element => {
    if (element.getBoundingClientRect().top > window.innerHeight) { element.classList.add('waiting'); observer.observe(element); }
  });
}

async function checkConnection() {
  const results = await Promise.allSettled([fetch('/health'), fetch('/demo-config')]);
  const online = results[0].status === 'fulfilled' && results[0].value.ok;
  $('connection-status').dataset.status = online ? 'online' : 'offline';
  $('connection-status').lastElementChild.textContent = online ? 'API connected' : 'API unavailable';
  if (results[1].status === 'fulfilled' && results[1].value.ok) {
    const config = await results[1].value.json();
    $('engine-mode').textContent = config.llm_enabled ? 'LLM enabled · fallback available' : 'Deterministic demo';
  } else $('engine-mode').textContent = 'Mode unavailable';
}
checkConnection().catch(() => { $('engine-mode').textContent = 'Mode unavailable'; });
const savedRequest = new URLSearchParams(location.search).get('request');
if (savedRequest) restore(savedRequest);
