# 🚀 Deploy & Test Guide

## Table of Contents
- [Phase 1: Local Testing](#phase-1-local-testing)
- [Phase 2: Docker Testing](#phase-2-docker-testing)
- [Phase 3: Deploy to Hugging Face Spaces](#phase-3-deploy-to-hugging-face-spaces)
- [Phase 4: Verify HF Space Deployment](#phase-4-verify-hf-space-deployment)
- [Phase 5: Pre-Submission Validation](#phase-5-pre-submission-validation)
- [Troubleshooting](#troubleshooting)

---

## Phase 1: Local Testing (Do This First)

### Step 1: Install Dependencies

```bash
cd D:\email_triage\email_triage
pip install -r requirements.txt
```

### Step 2: Start the Server

```bash
python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Verify Server is Running

Open these URLs in your browser:

| Endpoint | URL | Expected Response |
|----------|-----|-------------------|
| Health check | http://localhost:8000/health | `{"status": "healthy", ...}` |
| API docs | http://localhost:8000/docs | Swagger UI |
| Web UI | http://localhost:8000/web | Interactive interface |

Or via PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

### Step 4: Test Endpoints Manually

```powershell
# Test reset endpoint
Invoke-RestMethod -Uri "http://localhost:8000/openenv/reset" -Method Post -ContentType "application/json" -Body "{}"

# Test step endpoint
$body = @{ action = @{ task_id = 1; label = "spam" } } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/openenv/step" -Method Post -ContentType "application/json" -Body $body
```

### Step 5: Run Inference

Set environment variables:

```powershell
# OpenRouter (default - free, recommended)
# Get key at https://openrouter.ai/keys
$env:HF_TOKEN = "sk-or-v1-your-key"

# Run inference (uses OpenRouter defaults)
python inference.py --episodes 3

# Alternative: Hugging Face Router
$env:API_BASE_URL = "https://router.huggingface.co/v1"
$env:MODEL_NAME = "meta-llama/Meta-Llama-3-70B-Instruct"
$env:HF_TOKEN = "hf_your_token"
$env:ENV_BASE_URL = "http://localhost:8000"
python inference.py --episodes 3
```

**Expected output:**

```
[START] task=spam-classification env=email-triage model=meta-llama/Meta-Llama-3-70B-Instruct
[STEP] step=1 action={"task_id":1,"label":"spam"} reward=1.00 done=false error=null
[STEP] step=2 action={"task_id":2,"ranking":[1,2,0]} reward=0.60 done=false error=null
[STEP] step=3 action={"task_id":3,"action_type":"reply","reply_text":"..."} reward=0.80 done=true error=null
[END] success=true steps=3 score=0.80 rewards=1.00,0.60,0.80
```

### Step 6: Run Tests

```bash
pytest tests/ -v
```

---

## Phase 2: Docker Testing

### Step 1: Build Docker Image

```bash
docker build -t email-triage:latest .
```

### Step 2: Run Container

```bash
docker run -d -p 8000:8000 --name email-triage-test email-triage:latest
```

### Step 3: Verify Container

```powershell
# Check health
Invoke-RestMethod -Uri "http://localhost:8000/health"

# View logs
docker logs email-triage-test
```

### Step 4: Stop Container

```bash
docker stop email-triage-test
docker rm email-triage-test
```

---

## Phase 3: Deploy to Hugging Face Spaces

### Step 1: Get Hugging Face Token

1. Go to https://huggingface.co/settings/tokens
2. Create a new token with **write** access
3. Copy the token

### Step 2: Login via CLI

```bash
pip install huggingface_hub
huggingface-cli login
# Paste your token when prompted
```

### Step 3: Create a New Space

1. Go to https://huggingface.co/new-space
2. Fill in:
   - **Space name:** `email-triage`
   - **SDK:** Select **Docker**
   - **Visibility:** Public (required for competition)
3. Click **Create Space**

### Step 4: Push Code to Space

#### Option A: Using Git (Recommended)

```bash
# Navigate to project
cd D:\email_triage\email_triage

# Add HF Space as remote (replace YOUR_USERNAME)
git remote add hf-space https://huggingface.co/spaces/YOUR_USERNAME/email-triage

# Push to Space
git push hf-space main
```

#### Option B: Using Hugging Face Hub API

```python
from huggingface_hub import HfApi

api = HfApi()

# Upload entire folder (replace YOUR_USERNAME)
api.upload_folder(
    folder_path="D:/email_triage/email_triage",
    repo_id="YOUR_USERNAME/email-triage",
    repo_type="space"
)
```

#### Option C: Manual Upload via Web UI

1. Go to your Space: https://huggingface.co/spaces/YOUR_USERNAME/email-triage
2. Click **Files** → **Add file** → **Upload files**
3. Upload all files from your project directory
4. Commit changes

### Step 5: Configure Space Settings

In your Space settings, add these **Space Secrets**:

| Secret Name | Value |
|---|---|
| `API_BASE_URL` | `https://openrouter.ai/api/v1` |
| `MODEL_NAME` | `meta-llama/llama-3.2-3b-instruct:free` |
| `HF_TOKEN` | Your OpenRouter API key |

**How to add:**
1. Go to your Space → **Settings**
2. Scroll to **Variables and secrets**
3. Click **New secret**
4. Add each variable from the table above
5. Secrets are encrypted and only visible during build/runtime

### Step 6: Wait for Build

- The Space will automatically build your Dockerfile
- This takes **2–5 minutes**
- Watch the build logs in the Space page
- Status should change from **Building** → **Running**

---

## Phase 4: Verify HF Space Deployment

### Step 1: Check Health

```powershell
# Replace YOUR_USERNAME
Invoke-RestMethod -Uri "https://YOUR_USERNAME-email-triage.hf.space/health"
```

**Expected:** `{"status": "healthy", ...}`

### Step 2: Test Reset Endpoint

```powershell
Invoke-RestMethod -Uri "https://YOUR_USERNAME-email-triage.hf.space/openenv/reset" -Method Post
```

### Step 3: Test Step Endpoint

```powershell
$body = '{"action": {"task_id": 1, "label": "spam"}}'
Invoke-RestMethod -Uri "https://YOUR_USERNAME-email-triage.hf.space/openenv/step" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### Step 4: Run Inference Against HF Space

```powershell
$env:API_BASE_URL = "https://openrouter.ai/api/v1"
$env:MODEL_NAME = "meta-llama/llama-3.2-3b-instruct:free"
$env:HF_TOKEN = "sk-or-v1-your-key"
$env:ENV_BASE_URL = "https://YOUR_USERNAME-email-triage.hf.space"

python inference.py --episodes 3
```

---

## Phase 5: Pre-Submission Validation

### Run the Validation Script

```powershell
# Download validation script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/meta-pytorch/OpenEnv/main/scripts/validate-submission.sh" -OutFile "validate-submission.sh"

# Run it (requires Git Bash or WSL)
bash validate-submission.sh "https://YOUR_USERNAME-email-triage.hf.space"
```

### Manual Verification Checklist

```powershell
# 1. Space returns 200
$response = Invoke-WebRequest -Uri "https://YOUR_USERNAME-email-triage.hf.space"
$response.StatusCode  # Should be 200

# 2. Health check
Invoke-RestMethod -Uri "https://YOUR_USERNAME-email-triage.hf.space/health"

# 3. OpenEnv validate (if you have openenv-core)
openenv validate
```

---

## Quick Checklist

### Local Testing
- [ ] Server starts on port 8000
- [ ] Health check returns `"healthy"`
- [ ] `/openenv/reset` works
- [ ] `/openenv/step` works
- [ ] `inference.py` runs with correct `[START]/[STEP]/[END]` output format
- [ ] All tests pass (`pytest tests/`)

### Docker Testing
- [ ] `docker build` succeeds
- [ ] Container starts successfully
- [ ] Health check works inside container

### HF Spaces Deployment
- [ ] Space created (Docker SDK)
- [ ] Code pushed to Space
- [ ] Environment variables configured in Secrets
- [ ] Space status = "Running"
- [ ] Health check returns 200
- [ ] Reset/step endpoints work
- [ ] Inference runs against Space URL

### Pre-Submission
- [ ] Space URL responds to ping
- [ ] OpenEnv spec compliant
- [ ] Dockerfile builds cleanly
- [ ] Baseline inference produces scores
- [ ] 3+ tasks with graders verified

---

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| Space stuck "Building" | Missing dependency or Dockerfile error | Check build logs in Space page |
| Health check fails | Server not binding to correct interface | Verify server binds to `0.0.0.0`, not `localhost` |
| 500 error on `/step` | Missing or incorrect environment variables | Check Space secrets are set correctly |
| `inference.py` fails | Invalid API token or no API credits | Verify `HF_TOKEN` is valid and has access |
| Docker build fails | Files not in expected locations | Ensure all files are in project root, not subfolder |
| `openenv validate` warnings | Missing `uv.lock` on Windows | Non-critical — you have `requirements.txt` |
| Container exits immediately | Missing dependencies or syntax error | Run `docker logs email-triage-test` to see error |
| Space shows "Runtime error" | Port mismatch | Ensure `app_port: 8000` in `openenv.yaml` matches Dockerfile `EXPOSE` |

---

## Useful Commands

```bash
# Start server locally
python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Build Docker image
docker build -t email-triage:latest .

# Run Docker container
docker run -d -p 8000:8000 --name email-triage email-triage:latest

# View container logs
docker logs -f email-triage

# Stop container
docker stop email-triage && docker rm email-triage

# Run inference
python inference.py --episodes 3

# Run tests
pytest tests/ -v

# Check Python syntax
python -m py_compile inference.py models.py server/app.py
```

---

## Environment Variables Reference

| Variable | Description | Default | Required |
|---|---|---|---|
| `API_BASE_URL` | LLM API endpoint | `https://router.huggingface.co/v1` | ✅ |
| `MODEL_NAME` | Model identifier | `meta-llama/Meta-Llama-3-70B-Instruct` | ✅ |
| `HF_TOKEN` | Hugging Face API key | _(empty)_ | ✅ |
| `LOCAL_IMAGE_NAME` | Local Docker image name | `email-triage:latest` | ✅ |
| `ENV_BASE_URL` | Environment server URL | `http://localhost:8000` | ✅ |
| `NUM_EPISODES` | Number of episodes to run | `3` | ❌ |
| `DEBUG` | Enable debug logging | `false` | ❌ |

---

**Submission Deadline:** April 8th, 11:59 PM

Good luck! 🚀
