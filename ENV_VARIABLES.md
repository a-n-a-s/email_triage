# 🔑 Environment Variables Reference

## Overview

This document explains every environment variable used in the Email Triage project, where it's used, and why it's needed.

---

## Mandatory Variables (Required for Competition)

These 4 variables are **required by the competition rules** and must be defined in your environment.

### 1. `API_BASE_URL`

| Property | Value |
|---|---|
| **Description** | The API endpoint for the LLM service |
| **Default** | `https://router.huggingface.co/v1` |
| **Used in** | `inference.py` (line 51) |
| **Required by** | Competition rules ✅ |

**Where it's used:**

```python
# inference.py
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"

# Passed to OpenAI client
client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
```

**Why it's needed:**
- Tells the OpenAI client which API endpoint to call for LLM inference
- Hugging Face's router (`router.huggingface.co`) routes requests to available models
- Can be pointed at any OpenAI-compatible endpoint (OpenAI, HF, local servers)

**Example values:**
```bash
# Hugging Face router (recommended)
API_BASE_URL="https://router.huggingface.co/v1"

# OpenAI direct
API_BASE_URL="https://api.openai.com/v1"

# Local server
API_BASE_URL="http://localhost:11434/v1"
```

---

### 2. `MODEL_NAME`

| Property | Value |
|---|---|
| **Description** | The model identifier to use for inference |
| **Default** | `meta-llama/Meta-Llama-3-70B-Instruct` |
| **Used in** | `inference.py` (line 52) |
| **Required by** | Competition rules ✅ |

**Where it's used:**

```python
# inference.py
MODEL_NAME = os.getenv("MODEL_NAME") or "meta-llama/Meta-Llama-3-70B-Instruct"

# Passed to OpenAI client when making requests
response = client.chat.completions.create(
    model=MODEL_NAME,
    messages=[...],
    ...
)
```

**Why it's needed:**
- Specifies which LLM model to use for email triage tasks
- Different models have different capabilities and costs
- Competition uses this to reproduce your baseline scores

**Example values:**
```bash
# Meta Llama (recommended, free tier on HF)
MODEL_NAME="meta-llama/Meta-Llama-3-70B-Instruct"

# OpenAI GPT-4
MODEL_NAME="gpt-4-turbo"

# Qwen
MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
```

---

### 3. `HF_TOKEN`

| Property | Value |
|---|---|
| **Description** | Your Hugging Face API key / token |
| **Default** | _(empty)_ |
| **Used in** | `inference.py` (line 53) |
| **Required by** | Competition rules ✅ |

**Where it's used:**

```python
# inference.py
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "")

# Passed as authentication to OpenAI client
client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

# Validation check
if not HF_TOKEN:
    logger.error("❌ ERROR: HF_TOKEN or API_KEY not set")
    return
```

**Why it's needed:**
- Authenticates your API requests to Hugging Face's inference endpoints
- Required to access gated models (like Llama-3-70B)
- Alternative name `API_KEY` is also accepted for compatibility
- Without this, all LLM calls will fail with 401 Unauthorized

**How to get one:**
1. Go to https://huggingface.co/settings/tokens
2. Create a new token with **read** access (minimum)
3. Copy and set as environment variable:

```bash
# Windows PowerShell
$env:HF_TOKEN = "hf_your_token_here"

# Linux/Mac
export HF_TOKEN="hf_your_token_here"
```

---

### 4. `LOCAL_IMAGE_NAME`

| Property | Value |
|---|---|
| **Description** | The name of the local Docker image (if using `from_docker_image()`) |
| **Default** | `email-triage:latest` |
| **Used in** | `inference.py` (line 54) |
| **Required by** | Competition rules ✅ |

**Where it's used:**

```python
# inference.py
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME", "email-triage:latest")
```

**Why it's needed:**
- Defines the Docker image name when deploying via `from_docker_image()` method
- Used by the competition's automated testing infrastructure
- Ensures the correct image is pulled during evaluation

---

## Optional Variables (Configuration)

These variables customize runtime behavior but have sensible defaults.

### 5. `ENV_BASE_URL`

| Property | Value |
|---|---|
| **Description** | URL of the Email Triage environment server |
| **Default** | `http://localhost:8000` |
| **Used in** | `inference.py` (line 57), `tests/test_inference_actions.py` |

**Where it's used:**

```python
# inference.py
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")

# Used by EnvClient to connect to the environment server
env = EnvClient(base_url=ENV_BASE_URL)

# Health check
health = env.health()  # Calls ENV_BASE_URL/health

# Reset environment
obs = env.reset()  # Calls ENV_BASE_URL/openenv/reset

# Step action
result = env.step(action)  # Calls ENV_BASE_URL/openenv/step
```

**Why it's needed:**
- Tells the inference script where the Email Triage environment server is running
- Changes when deploying to HF Spaces (points to the Space URL instead of localhost)

**Example values:**
```bash
# Local development
ENV_BASE_URL="http://localhost:8000"

# Docker container (from docker-compose)
ENV_BASE_URL="http://api:8000"

# Hugging Face Space deployment
ENV_BASE_URL="https://YOUR_USERNAME-email-triage.hf.space"
```

---

### 6. `NUM_EPISODES`

| Property | Value |
|---|---|
| **Description** | Number of episodes to run during inference |
| **Default** | `3` |
| **Used in** | `inference.py` (line 59) |

**Where it's used:**

```python
# inference.py
NUM_EPISODES = int(os.getenv("NUM_EPISODES", "3"))

# Controls the main loop
for ep in range(num_episodes):
    result = run_episode(agent, env, ep)
    all_results.append(result)
```

**Why it's needed:**
- Controls how many times the inference loop runs
- More episodes = more reliable average scores but longer runtime
- Competition may re-run your script multiple times

**Example usage:**
```bash
# Run 5 episodes instead of 3
$env:NUM_EPISODES = "5"
python inference.py
```

---

### 7. `DEBUG`

| Property | Value |
|---|---|
| **Description** | Enable debug logging output |
| **Default** | `false` |
| **Used in** | `inference.py` (line 70) |

**Where it's used:**

```python
# inference.py
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Controls logging level
logging.basicConfig(
    level=logging.INFO if DEBUG else logging.WARNING,
    ...
)

# Controls verbose in agent
if DEBUG:
    logger.debug(f"Prompt (truncated): {prompt[:300]}...")
    logger.debug(f"LLM Response: {response_text[:200]}...")
    logger.debug(f"Parsed Action: {action}")
```

**Why it's needed:**
- When `true`: Shows detailed logs (prompts, responses, actions)
- When `false`: Only shows warnings and errors (cleaner output)
- Useful for debugging but adds noise to stdout

**Example usage:**
```bash
# Enable debug logging
$env:DEBUG = "true"
python inference.py
```

---

## Server-Side Variables

These are used by the server components, not the inference script.

### 8. `EMAIL_TRIAGE_DB`

| Property | Value |
|---|---|
| **Description** | Path to the SQLite database file |
| **Default** | `email_triage.db` |
| **Used in** | `server/database.py` (line 18), `streamlit_analytics.py` |

**Where it's used:**

```python
# server/database.py
DATABASE_PATH = os.getenv("EMAIL_TRIAGE_DB", "email_triage.db")

# Opens database connection
conn = sqlite3.connect(DATABASE_PATH)
```

**Why it's needed:**
- Specifies where to store episode history and analytics data
- Useful in Docker to mount database as persistent volume
- Streamlit dashboard reads from same database

**Example values:**
```bash
# Default (current directory)
EMAIL_TRIAGE_DB="email_triage.db"

# Docker volume mount
EMAIL_TRIAGE_DB="/app/email_triage.db"

# Custom location
EMAIL_TRIAGE_DB="/data/email_triage.db"
```

---

## Dockerfile Variables

These are defined in the `Dockerfile` for HF Spaces deployment.

```dockerfile
# Dockerfile
ENV API_BASE_URL="https://router.huggingface.co/v1"
ENV MODEL_NAME="meta-llama/Meta-Llama-3-70B-Instruct"
ENV HF_TOKEN=""
ENV LOCAL_IMAGE_NAME="email-triage:latest"
ENV ENV_BASE_URL="http://localhost:8000"
```

**Why they're in Dockerfile:**
- Provides default values when container starts
- Can be overridden by HF Space secrets (recommended)
- Ensures container works out-of-the-box for testing

---

## Complete `.env` File Template

Create a `.env` file in your project root (copy from `.env.example`):

```bash
# ================================
# LLM API Configuration (MANDATORY)
# ================================

# API endpoint for LLM service
API_BASE_URL="https://router.huggingface.co/v1"

# Model to use for inference
MODEL_NAME="meta-llama/Meta-Llama-3-70B-Instruct"

# Your Hugging Face API token
HF_TOKEN="hf_your_token_here"

# Local Docker image name
LOCAL_IMAGE_NAME="email-triage:latest"

# ================================
# Environment Configuration
# ================================

# URL of Email Triage server
ENV_BASE_URL="http://localhost:8000"

# Number of episodes to run
NUM_EPISODES="3"

# Enable debug logging (true/false)
DEBUG="false"

# ================================
# Server Configuration
# ================================

# Database file path
EMAIL_TRIAGE_DB="email_triage.db"
```

---

## Where Each Variable is Used (Summary Table)

| Variable | File | Line | Purpose |
|---|---|---|---|
| `API_BASE_URL` | `inference.py` | 51 | LLM API endpoint |
| `MODEL_NAME` | `inference.py` | 52 | Model identifier |
| `HF_TOKEN` | `inference.py` | 53 | API authentication |
| `LOCAL_IMAGE_NAME` | `inference.py` | 54 | Docker image name |
| `ENV_BASE_URL` | `inference.py` | 57 | Environment server URL |
| `NUM_EPISODES` | `inference.py` | 59 | Episode count |
| `DEBUG` | `inference.py` | 70 | Debug logging toggle |
| `EMAIL_TRIAGE_DB` | `server/database.py` | 18 | Database path |

---

## Competition Requirements

### Must be defined (MANDATORY):
- ✅ `API_BASE_URL`
- ✅ `MODEL_NAME`
- ✅ `HF_TOKEN`
- ✅ `LOCAL_IMAGE_NAME`

### Should be set for deployment:
- ⚠️ `ENV_BASE_URL` (defaults to localhost, change for HF Spaces)
- ⚠️ `EMAIL_TRIAGE_DB` (defaults to current directory)

### Optional:
- `NUM_EPISODES` (defaults to 3)
- `DEBUG` (defaults to false)

---

## HF Spaces Secrets Configuration

When deploying to Hugging Face Spaces, add these as **Space Secrets** (not in code):

| Secret | Value | Where to Add |
|---|---|---|
| `API_BASE_URL` | `https://router.huggingface.co/v1` | Space → Settings → Variables and secrets |
| `MODEL_NAME` | `meta-llama/Meta-Llama-3-70B-Instruct` | Space → Settings → Variables and secrets |
| `HF_TOKEN` | `hf_your_token_here` | Space → Settings → Variables and secrets (mark as secret!) |

**Important:**
- `HF_TOKEN` must be a **secret** (never expose in logs or UI)
- Other variables can be regular **variables** (visible in build logs)
- Secrets are encrypted and injected at runtime

---

## Common Issues

### Issue 1: "HF_TOKEN or API_KEY not set"

**Cause:** Environment variable not defined

**Fix:**
```powershell
$env:HF_TOKEN = "hf_your_token_here"
```

### Issue 2: "401 Unauthorized" from API

**Cause:** Invalid or expired token

**Fix:** Regenerate token at https://huggingface.co/settings/tokens

### Issue 3: "Connection refused" on ENV_BASE_URL

**Cause:** Environment server not running at specified URL

**Fix:**
```bash
# Start server first
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000

# Then run inference
python inference.py
```

### Issue 4: Wrong model in output

**Cause:** `MODEL_NAME` not matching what you expect

**Fix:**
```powershell
# Verify it's set correctly
echo $env:MODEL_NAME
```
