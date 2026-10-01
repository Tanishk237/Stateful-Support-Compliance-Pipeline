// This view consumes real node-boundary events; it never simulates execution.
const nodes = [...document.querySelectorAll('[data-node]')];
const snapshots = new Map();
let selected;
const status = document.querySelector('#flow-status');
const names = Object.fromEntries(nodes.map(node => [node.dataset.node, node.querySelector('strong').textContent]));

function paint(step, phase, label) {
  const node = nodes.find(item => item.dataset.node === step);
  if (!node) return;
  node.dataset.status = phase;
  node.querySelector('.node-status').textContent = label;
}

function inspect(step) {
  selected = step;
  nodes.forEach(node => node.setAttribute('aria-pressed', String(node.dataset.node === step)));
  document.querySelector('#node-inspector-title').textContent = names[step];
  const snapshot = snapshots.get(step);
  const output = document.querySelector('#node-inspector-output');
  document.querySelector('#node-inspector-note').textContent = snapshot
    ? 'Backend state after this node. Saved requests show their activity record instead of a historical state snapshot.'
    : 'This node has not completed in this run. Inactive branches remain visible so you can explore every route.';
  output.hidden = !snapshot;
  output.textContent = snapshot ? JSON.stringify(snapshot, null, 2) : '';
}

nodes.forEach(node => node.addEventListener('click', () => {
  inspect(node.dataset.node);
  document.querySelector('#node-inspector').open = true;
}));

export function resetGraph(resuming = false) {
  if (!resuming) {
    snapshots.clear();
    nodes.forEach(node => paint(node.dataset.node, 'waiting', 'Waiting'));
  } else {
    for (const step of ['validate', 'verify', 'respond', 'billing_review']) {
      snapshots.delete(step);
      paint(step, 'waiting', 'Waiting');
    }
    paint('clarify', 'done', 'Answer submitted · resuming');
  }
  if (selected) inspect(selected);
  status.textContent = resuming ? 'Resuming from validation' : 'Connecting to backend';
}

function nodeOutput(step, state) {
  switch (step) {
    case 'compliance': return { ...state.compliance_result, redacted_email: state.redacted_email };
    case 'extract': return { fields: state.extracted_information, source: state.extraction_source, prompt: state.extraction_prompt_version };
    case 'validate': return { status: state.validation_status, missing_fields: state.missing_fields };
    case 'verify': return state.business_verification;
    case 'clarify': return { question: state.clarification_question, missing_fields: state.missing_fields, attempt: state.retry_count };
    case 'respond': return state.customer_response;
    default: return state.escalation_ticket;
  }
}

export function graphEvent(event) {
  if (event.type === 'step_started') {
    paint(event.step, 'running', 'Running now');
    status.textContent = `${names[event.step]} is running`;
  } else if (event.type === 'step_completed') {
    snapshots.set(event.step, nodeOutput(event.step, event.state));
    paint(event.step, 'done', `Completed · ${event.duration_ms.toFixed(1)} ms`);
    if (selected === event.step) inspect(selected);
  } else if (event.type === 'complete') {
    finishGraph(event.state.route);
  }
}

function finishGraph(route) {
  nodes.filter(node => node.dataset.status !== 'done').forEach(node => paint(node.dataset.node, 'skipped', 'Not taken'));
  status.textContent = route === 'clarify' ? 'Paused · waiting for your answer' : route === 'pending' ? 'Incomplete · last saved checkpoint' : 'Complete · saved to SQLite';
}

export function graphError() {
  nodes.filter(node => node.dataset.status === 'running').forEach(node => paint(node.dataset.node, 'error', 'Interrupted'));
  status.textContent = 'Connection or processing interrupted';
}

export function restoreGraph(state) {
  resetGraph();
  for (const event of state.execution_history) {
    const step = event.step === 'escalate' || event.step === 'escalation' ? state.route : event.step;
    if (!names[step]) continue;
    snapshots.set(step, [...(snapshots.get(step) || []), event]);
    paint(step, 'done', 'Completed · saved activity');
  }
  finishGraph(state.route);
  if (selected) inspect(selected);
}
