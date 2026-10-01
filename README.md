# Support & Compliance Pipeline

A focused portfolio demo for customer billing complaints. The project accepts a complaint email, removes sensitive data before any external LLM call, extracts a typed payload, validates and verifies the claim, then returns a response or creates an escalation.

The same workflow powers a CLI and **Resolve**, an interactive portfolio website served by FastAPI. SQLite stores each request, its execution history, and escalation tickets. The frontend is plain HTML, CSS, and JavaScript: no Node install, frontend build step, or second server.

## Demo Flow

```text
Billing complaint
  → compliance check and redaction
  ├─ sensitive data → compliance_escalation
  └─ safe → structured extraction → validation
             ├─ missing fields → clarify → resume validation
             └─ complete → business verification
                            ├─ all checks pass → respond
                            └─ check fails → billing_review
```

The demo deliberately handles one use case: billing discrepancies. It does not send real emails, issue refunds, or connect to a production billing platform.

## What It Demonstrates

- Stateful orchestration with LangGraph and a shared Pydantic model.
- Compliance-first processing: PII is detected and redacted before external LLM use.
- Structured LLM extraction with schema validation, prompt versioning, clear errors, and deterministic fallback.
- Resumable clarification that merges the customer's answer and continues from validation.
- Business verification of identity, claimed amount, expected amount, account status, and calculated discrepancy.
- Clear verification reason codes such as `IDENTITY_MISMATCH`, `ACCOUNT_INACTIVE`, and `DISCREPANCY_MISMATCH`.
- Four explicit outcome routes: `respond`, `clarify`, `billing_review`, and `compliance_escalation`.
- Lightweight SQLite persistence and simple API/UI entry points.
- Live backend graph events: see active nodes, branches, timings, and per-node results.
- Browser speech-to-text with editable transcription, plus four ready-to-run scenarios.

## Project Structure

```text
├── api.py                       # FastAPI routes
├── frontend/index.html          # Portfolio page and interactive playground
├── frontend/assets/             # Styles, app/graph/speech JS, self-hosted assets
├── service.py                   # Shared application service
├── persistence.py               # SQLite store
├── graph/workflow.py            # LangGraph workflow and routing
├── nodes/                        # Workflow steps
├── state/workflow_state.py      # Shared state model
├── models.py                    # Typed workflow results
├── mock_db.py                   # Demo billing records
├── prompts.py                   # Versioned prompts
├── pii.py                       # PII detection and redaction
├── main.py                      # CLI
├── sample_emails/               # Demo inputs
├── tests/                       # Node, graph, API, and persistence tests
├── data/                        # Local SQLite database (generated)
├── scripts/dev                  # Start website + API with one command
└── Dockerfile                   # One-container website + API
```

## Quick Start

```bash
python3 -m venv .venv            # Python 3.11+ recommended
source .venv/bin/activate
pip install -r requirements.txt
```

The application works without an LLM key by using deterministic extraction and response fallbacks.

Start the API and visual demo together:

```bash
./scripts/dev
```

Open **http://127.0.0.1:8501**. The website and API now share one FastAPI process. API docs are at `/docs`. Press `Ctrl+C` to stop. If the port is occupied, use `SUPPORT_PORT=8502 ./scripts/dev`; the launcher never kills an existing process. `SUPPORT_HOST` changes the bind address and `PORT` is also accepted. The old separate API/UI port settings are no longer used.

### Visual Demo

The playground includes four scenarios: verified billing discrepancy, missing account details, synthetic sensitive data, and a customer-name mismatch. It displays the **actual backend graph** as nodes start and finish, including the clarification pause/resume path. Click a node to inspect its output. Deterministic runs often finish in milliseconds; no artificial delays are added. The result tabs show extracted fields, privacy/business checks, and execution history. Copy the output, download the state, or reopen a saved request by ID (also retained in the URL).

Use **Clear → Dictate your issue** to enter a complaint by voice. Stop recording, review names/account numbers/amounts, then submit. This uses the browser's Speech Recognition API, which is not supported in every browser and needs microphone permission plus HTTPS or localhost. Unsupported browsers keep the text input fully usable. Audio may be processed by the browser's speech provider; our backend only receives the reviewed text. Do not dictate real sensitive data.

The page includes light/dark themes, keyboard-accessible controls, a motion pause button, and support for reduced-motion preferences.

### FastAPI Backend

```bash
uvicorn api:app --reload
```

Open `http://localhost:8000/docs` for the interactive API documentation.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/complaints` | Create and run a billing complaint |
| `POST` | `/complaints/{request_id}/clarification` | Submit requested missing fields and resume |
| `GET` | `/complaints/{request_id}` | Read the latest saved state |
| `GET` | `/health` | Check the API and SQLite connection |
| `POST` | `/complaints/stream` | Run a complaint with live server-sent events |
| `POST` | `/complaints/{request_id}/clarification/stream` | Resume with live server-sent events |
| `GET` | `/demo-config` | Report whether LLM mode is enabled; no secrets |

Streaming requests take the same JSON as their non-streaming counterparts. Events are `request_started`, `step_started`, `step_completed` (node output state and elapsed milliseconds), `complete` (persisted final state), or `error`. Validation/lookup errors return normal HTTP errors before streaming begins. Runtime errors produce an `error` event instead of a false completion. Node snapshots are live-only; reopened requests display saved activity. Disable proxy buffering for the streaming endpoints if your host buffers responses.

Create a complaint:

```bash
curl -X POST http://localhost:8000/complaints \
  -H "Content-Type: application/json" \
  -d '{"email":"Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100."}'
```

Resume a complaint that returned the `clarify` route:

```bash
curl -X POST http://localhost:8000/complaints/REQUEST_ID/clarification \
  -H "Content-Type: application/json" \
  -d '{"answers":{"account_id":"ACC1023"}}'
```

### CLI

```bash
python main.py --demo happy
python main.py --demo missing_account
python main.py --demo credit_card
python main.py --file sample_emails/happy_path.txt
python main.py --demo happy --auto --json
```

## LLM Configuration

Copy `.env.example` to `.env`. OpenAI is used by default when no custom base URL is provided; any OpenAI-compatible provider can be selected with the same settings.

```env
USE_LLM=1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
LLM_BASE_URL=
DATABASE_PATH=data/support_pipeline.db
```

If configuration, network access, JSON parsing, or schema validation fails, the error is recorded in the workflow state and deterministic extraction is used. Unsafe input is escalated before extraction, so it cannot reach the configured provider.

## Business Verification

The mock billing records include the customer name, actual bill, expected bill, and account status. Verification checks:

1. The account exists.
2. The customer name matches the account.
3. The claimed amount matches the recorded actual bill.
4. The expected amount matches the recorded expected bill.
5. The account is active.
6. The customer-reported discrepancy matches the recorded discrepancy.

The result contains booleans for each check, both discrepancy values, and reason codes. Only a complete match reaches `respond`; other safe requests reach `billing_review`.

## SQLite Persistence

The default database is `data/support_pipeline.db`. It has three intentionally small tables:

- `workflow_states`: the latest Pydantic state for each request (after each completed node on the streaming path).
- `execution_history`: ordered workflow events for each request.
- `escalation_tickets`: billing and compliance escalation details.

Set `DATABASE_PATH` to use a different file. No database server or migration tool is required for this demo; tables are created automatically.

## Tests

```bash
pytest -q
```

The tests cover extraction fallback, compliance ordering, clarification resume, verification reason codes, graph routing, SQLite persistence, static assets, and streaming/API contracts. See [frontend/README.md](frontend/README.md) for frontend structure and a browser smoke-test checklist.

## Simple Deployment

Build and run the entire website and API together:

```bash
docker build -t billing-workflow-demo .
docker run --rm -p 8000:8000 -v billing-demo-data:/app/data billing-workflow-demo
```

Open `http://localhost:8000`. Deploy the same Dockerfile to a container host; it respects the host's `PORT` environment variable. Configure `/health` as the health check, attach a persistent disk at `/app/data`, and enable HTTPS for speech input. Set LLM secrets in the host environment, never in frontend code. Leave `USE_LLM=0` for a free deterministic showcase.

This is deliberately a **public, no-auth demonstration**, not a production support system. Use synthetic data only: request IDs are not authorization, the database contains original input, the PII detector is pattern-based, and the public API is not rate-limited. Prefer deterministic mode for a public demo; enabling paid LLM calls requires host-level abuse controls and spend limits. Ticket details persist in SQLite; the workflow also writes text copies in `escalation_tickets/` (mount that directory too if you need the copies across container restarts).
