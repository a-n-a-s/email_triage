---
title: Email Triage Environment
emoji: 📧
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8000
pinned: false
---

# 📧 Email Triage Environment

A real-world email prioritization environment for training and evaluating AI agents through the OpenEnv step()/reset()/state() API.

---

## Environment Description

Email Triage simulates a task that knowledge workers perform daily: processing an inbox by classifying spam, prioritizing by urgency, and composing professional replies. Agents must understand natural language, make judgment calls about legitimacy and priority, and generate context-appropriate responses.

**Why this environment?** Email triage tests fundamental agent capabilities — text classification, decision-making under uncertainty, and natural language generation — in a domain anyone can evaluate. Unlike toy environments, this has real utility: organizations actually need agents that can triage communications reliably and safely.

---

## Action Space

| Field | Type | Description |
|---|---|---|
| `task_id` | `int` (optional) | Task being attempted: 1 (spam), 2 (ranking), 3 (reply) |
| `label` | `str` (optional) | Task 1: `"spam"` or `"not_spam"` |
| `ranking` | `list[int]` (optional) | Task 2: Email indices ordered by urgency, e.g. `[1, 0, 2]` |
| `action_type` | `str` (optional) | Task 3: `"reply"`, `"forward"`, `"archive"`, or `"delete"` |
| `reply_text` | `str` (optional) | Task 3: Professional reply text when action_type is `"reply"` |

```json
{"task_id": 1, "label": "spam"}
```

---

## Observation Space

| Field | Type | Description |
|---|---|---|
| `task_id` | `int` | Current task ID (1, 2, or 3) |
| `task_description` | `str` | Plain English description of what to do |
| `emails` | `list[dict]` | List of email dicts to process (each has `id`, `subject`, `sender`, `body`) |
| `reward` | `float` | Reward for the last action (0.0 to 1.0) |
| `done` | `bool` | True when episode is complete |
| `feedback` | `str` | Human-readable explanation of the reward |

---

## Tasks

### Task 1: Spam Classification (Easy)

Classify a single email as `"spam"` or `"not_spam"`. Spam indicators include unrealistic rewards, false urgency, suspicious senders, and phishing attempts.

**Scoring:** Correct = 1.0, Wrong = 0.0, First-try efficiency bonus = +0.1 (capped at 1.0), Invalid label = -0.2.

### Task 2: Urgency Ranking (Medium)

Rank 3 emails by urgency from most to least urgent. Urgency considerations: production/server issues = highest, time-sensitive business matters = medium, newsletters/general info = lowest.

**Scoring:** 3/3 correct = 1.0, 2/3 correct = 0.6, 1/3 correct = 0.3, 0/3 correct = 0.0, Invalid ranking = -0.2.

### Task 3: Action & Reply (Hard)

Read an email and choose an action (`reply`, `forward`, `archive`, `delete`). If action is `"reply"`, write a professional reply. The grader scores action correctness (0.5) and reply quality based on keyword coverage (0.0–0.5).

**Scoring:** Total = action score + reply quality score (0.0–1.0).

---

## Setup and Usage

### Local Setup

```bash
# 1. Install dependencies
pip install openenv-core fastapi uvicorn pydantic

# 2. Start the environment server
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Run Inference

The `inference.py` script in the project root runs baseline inference. It requires an LLM API and emits structured stdout in the competition format (`[START]`, `[STEP]`, `[END]`).

```bash
# Option 1: Ollama (local, free, no rate limits)
# Install from https://ollama.com/download/windows
ollama pull llama3.2
python inference.py

# Option 2: OpenRouter
export API_BASE_URL="https://openrouter.ai/api/v1"
export MODEL_NAME="meta-llama/llama-3.1-8b-instruct:free"
export HF_TOKEN="sk-or-v1-your-key"
python inference.py

# Option 3: Hugging Face Router
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="meta-llama/Meta-Llama-3-70B-Instruct"
export HF_TOKEN="hf_your_token"
python inference.py
```

### Inference Output Format

```
[START] task=spam-classification env=email-triage model=llama3.2
[STEP] step=1 action={"task_id":1,"label":"spam"} reward=1.00 done=false error=null
[STEP] step=2 action={"task_id":2,"ranking":[0,1,2]} reward=1.00 done=false error=null
[STEP] step=3 action={"task_id":3,"action_type":"reply","reply_text":"..."} reward=0.75 done=true error=null
[END] success=true steps=3 score=0.92 rewards=1.00,1.00,0.75
```

### Docker

```bash
# Build
docker build -t email-triage:latest .

# Run
docker run -p 8000:8000 email-triage:latest
```

### Deploy to Hugging Face Spaces

1. Create a Space at https://huggingface.co/new-space with SDK = **Docker**
2. Push the repository files to the Space
3. Add Space Secrets: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
4. The Space builds automatically and starts on `app_port: 8000`

### Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/openenv/reset` | POST | Reset environment, start new episode |
| `/openenv/step` | POST | Execute an action, get observation + reward |
| `/openenv/state` | GET | Get current environment state |
| `/openenv/schema` | GET | Get action/observation JSON schemas |
| `/docs` | GET | OpenAPI/Swagger documentation |
| `/web` | GET | Interactive web interface |

---

## Baseline Scores

Results from running `inference.py` with Ollama `llama3.2` (3B parameter model, local inference):

| Episode | Task 1 (Spam) | Task 2 (Ranking) | Task 3 (Reply) | Average |
|---|---|---|---|---|
| 1 | 1.00 | 0.30 | 0.50 | 0.60 |
| 2 | 1.00 | 0.00 | 0.75 | 0.58 |
| 3 | 1.00 | 1.00 | 0.50 | 0.83 |
| **Avg** | **1.00** | **0.43** | **0.58** | **0.67** |

Scores vary per episode because emails are randomly generated from 100+ templates. Task 1 (spam) is consistently high. Task 2 (ranking) and Task 3 (reply) depend on LLM quality. Larger models achieve higher scores.

---

## Architecture

```
email_triage/
├── inference.py                    # Baseline inference (competition format)
├── models.py                       # Pydantic Action/Observation types
├── openenv.yaml                    # HF Space metadata
├── Dockerfile                      # Root-level Dockerfile for deployment
├── server/
│   ├── app.py                      # FastAPI server + OpenEnv routes
│   ├── email_triage_environment.py # Core environment + 100+ email templates
│   └── database.py                 # SQLite episode persistence
├── tests/
│   └── test_graders.py             # Grader unit tests
└── streamlit_analytics.py          # Analytics dashboard
```

---

## Features

- **100+ dynamic email templates** across spam, legitimate, ranking, and reply categories
- **Adversarial examples** (sophisticated phishing, spoofed senders) that challenge frontier models
- **Partial credit grading** — graders provide meaningful signal across the full trajectory, not just binary pass/fail
- **Efficiency bonuses** for first-try correct answers
- **Randomized content** — each `reset()` generates new emails, preventing memorization
- **SQLite persistence** — episode history stored for analytics
- **Streamlit dashboard** — visualize model performance over time

---

## License

BSD-3-Clause

---

## Acknowledgments

Built with [OpenEnv](https://github.com/meta-pytorch/OpenEnv) for the OpenEnv Competition.
