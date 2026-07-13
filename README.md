# Support & Compliance Pipeline

A CLI-based workflow for handling customer billing complaint emails.

The pipeline extracts complaint details, validates required fields, verifies the claim against a mock billing database, checks for PII/compliance risk, and then either:

- generates a customer response
- creates an internal escalation ticket

The workflow is built with LangGraph and uses a shared `WorkflowState` object across every step.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --demo happy
```

Run tests:

```bash
.venv/bin/python -m pytest -q
```

## How It Works

```text
Email
  |
  v
Extract -> Validate -> Clarify if missing data
  |
  v
Verify billing claim
  |
  v
Compliance / PII check
  |
  +--> Safe + verified     -> Customer response
  |
  +--> Missing / mismatch /
       unsafe / invalid    -> Escalation ticket
```

## Main Features

- LLM-based extraction when `USE_LLM=1`
- deterministic regex fallback when the LLM fails
- request id generation for every run
- clarification loop for missing fields
- mock billing verification
- regex-based PII detection
- saved run logs in `logs/`
- saved escalation tickets in `escalation_tickets/`
- sample emails in `sample_emails/`

## Project Structure

```text
graph/workflow.py          LangGraph workflow and routing
main.py                    CLI entry point
state/workflow_state.py    Shared state model

nodes/extract.py           Extracts structured email data
nodes/validate.py          Validates required fields
nodes/clarify.py           Handles missing information retries
nodes/verify.py            Checks mock billing database
nodes/compliance.py        Checks PII/compliance risk
nodes/response.py          Generates customer response
nodes/escalation.py        Creates and saves escalation tickets

mock_db.py                 Mock customer billing records
pii.py                     Regex PII detection
prompts.py                 LLM prompt builders
logger.py                  Run log writer
config.py                  Environment config
tests/                     Test suite
```

## Workflow State

The central state object is `WorkflowState`.

Important fields:

- `request_id`: generated id for the run
- `raw_email`: original email text
- `extracted_information`: extracted complaint data
- `missing_fields`: fields that need clarification
- `retry_count`: clarification retry count
- `validation_status`: `pending`, `passed`, `clarification`, or `failed`
- `verification_status`: `pending`, `verified`, `mismatch`, or `not_found`
- `compliance_status`: `pending`, `safe`, `high`, or `critical`
- `route`: final route, usually `response` or `escalate`
- `final_output`: customer response or escalation ticket
- `execution_history`: audit trail of each step

## Run Commands

Built-in happy path:

```bash
python main.py --demo happy
```

Built-in scenarios:

```bash
python main.py --demo missing_account
python main.py --demo missing_amount
python main.py --demo credit_card
python main.py --demo wrong_account
```

Sample email files:

```bash
python main.py --file sample_emails/happy_path.txt
python main.py --file sample_emails/missing_account.txt
python main.py --file sample_emails/missing_amount.txt
python main.py --file sample_emails/credit_card_risk.txt
python main.py --file sample_emails/pan_risk.txt
python main.py --file sample_emails/wrong_account.txt
python main.py --file sample_emails/customer_mismatch.txt
```

Inline email:

```bash
python main.py --email 'Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100.'
```

Important: use single quotes for inline emails that contain dollar amounts. In double quotes, your shell may remove `$120` before Python receives it.

Other useful options:

```bash
python main.py --demo happy --json
python main.py --demo happy --no-log
python main.py --demo happy --auto
python main.py
```

## LLM Setup

Create or edit `.env`:

```env
USE_LLM=1
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
```

LLM calls happen in two places:

- extraction: `nodes/extract.py`
- customer response generation: `nodes/response.py`

Verification, compliance, and escalation are deterministic by design.

The CLI shows whether the LLM was used:

```text
LLM mode: enabled (nvidia/nemotron-3-ultra-550b-a55b)
Extraction engine: llm
Extracted amounts: claimed=120.0, expected=100.0
```

If the LLM fails, the pipeline records the reason and falls back:

```text
Extraction engine: fallback (APIConnectionError: Connection error.)
```

## Outputs

Run logs are saved in:

```text
logs/
```

Escalation tickets are saved in:

```text
escalation_tickets/
```

Customer responses are printed in the terminal and included in the run log.

## Test Coverage

The test suite covers:

- happy path
- missing account
- missing amount
- retry limit
- credit card / PII risk
- wrong account
- invalid LLM JSON fallback
- full graph execution
- request id generation
- log and escalation ticket output

Run:

```bash
.venv/bin/python -m pytest -q
```

## Future Improvements

- replace the mock database with a real billing integration
- add a web UI for support agents
- add persistent workflow storage
- add human approval before sending responses
- redact PII before saving tickets/logs
- add richer billing cases like refunds, credits, and invoice periods
