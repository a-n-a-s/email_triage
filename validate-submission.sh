#!/usr/bin/env bash
#
# validate-submission.sh — OpenEnv Submission Validator
#
# Checks that your HF Space is live, Docker image builds, and submission requirements pass.
#
# Prerequisites:
#   - Docker:       https://docs.docker.com/get-docker/
#   - openenv-core: pip install openenv-core
#   - curl, jq, python3
#
# Run:
#   ./validate-submission.sh <ping_url> [repo_dir]
#
# Examples:
#   ./validate-submission.sh https://akanaspro-email-triage.hf.space
#   ./validate-submission.sh https://akanaspro-email-triage.hf.space /path/to/repo
#

set -uo pipefail

DOCKER_BUILD_TIMEOUT=600
PING_URL="${1:-}"
REPO_DIR="${2:-.}"

if [ -z "$PING_URL" ]; then
  echo "Usage: $0 <hf_space_url> [repo_dir]"
  echo "Example: $0 https://akanaspro-email-triage.hf.space"
  exit 1
fi

PASS=0
FAIL=0
WARN=0

# Colors
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BOLD='' NC=''
fi

pass_check() { echo -e "  ${GREEN}✅ PASS${NC}  $1"; PASS=$((PASS + 1)); }
fail_check() { echo -e "  ${RED}❌ FAIL${NC}  $1"; FAIL=$((FAIL + 1)); }
warn_check() { echo -e "  ${YELLOW}⚠️  WARN${NC}  $1"; WARN=$((WARN + 1)); }

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  📋  OPENENV SUBMISSION VALIDATOR                       ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo -e "║  🌐  Space : ${BOLD}${PING_URL}${NC}                             ║"
echo -e "║  📁  Repo  : ${BOLD}${REPO_DIR}${NC}                                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ──────────────────────────────────────────────────────────────
# 1. HF Space Deploys
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[1/11] HF Space Deploys${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$PING_URL" --max-time 30 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
  pass_check "Space returns HTTP 200"
else
  fail_check "Space returned HTTP $HTTP_CODE (expected 200)"
fi

# ──────────────────────────────────────────────────────────────
# 2. Health Endpoint
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[2/11] Health Endpoint${NC}"
HEALTH=$(curl -sf "$PING_URL/health" --max-time 30 2>/dev/null)
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='healthy'" 2>/dev/null; then
  pass_check "/health returns healthy status"
else
  fail_check "/health did not return healthy status"
fi

# ──────────────────────────────────────────────────────────────
# 3. Reset Endpoint
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[3/11] Reset Endpoint (/openenv/reset)${NC}"
RESET_RESP=$(curl -sf -X POST "$PING_URL/openenv/reset" -H "Content-Type: application/json" -d '{}' --max-time 30 2>/dev/null)
if echo "$RESET_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'observation' in d; assert 'task_id' in d['observation']; assert 'emails' in d['observation']" 2>/dev/null; then
  pass_check "/openenv/reset returns valid observation"
else
  fail_check "/openenv/reset did not return valid observation"
fi

# ──────────────────────────────────────────────────────────────
# 4. Step Endpoint (Task 1: Spam)
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[4/11] Step Endpoint - Task 1 (Spam)${NC}"
STEP1=$(curl -sf -X POST "$PING_URL/openenv/step" \
  -H "Content-Type: application/json" \
  -d '{"action":{"task_id":1,"label":"spam"}}' \
  --max-time 30 2>/dev/null)
REWARD1=$(echo "$STEP1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reward',''))" 2>/dev/null)
TASK2=$(echo "$STEP1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['observation'].get('task_id',''))" 2>/dev/null)
if [ "$REWARD1" != "" ] && [ "$TASK2" = "2" ]; then
  pass_check "Task 1: reward=$REWARD1, advanced to Task 2"
else
  fail_check "Task 1: invalid response (reward=$REWARD1, next_task=$TASK2)"
fi

# ──────────────────────────────────────────────────────────────
# 5. Step Endpoint (Task 2: Ranking)
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[5/11] Step Endpoint - Task 2 (Ranking)${NC}"
STEP2=$(curl -sf -X POST "$PING_URL/openenv/step" \
  -H "Content-Type: application/json" \
  -d '{"action":{"task_id":2,"ranking":[0,1,2]}}' \
  --max-time 30 2>/dev/null)
REWARD2=$(echo "$STEP2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reward',''))" 2>/dev/null)
TASK3=$(echo "$STEP2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['observation'].get('task_id',''))" 2>/dev/null)
if [ "$REWARD2" != "" ] && [ "$TASK3" = "3" ]; then
  pass_check "Task 2: reward=$REWARD2, advanced to Task 3"
else
  fail_check "Task 2: invalid response (reward=$REWARD2, next_task=$TASK3)"
fi

# ──────────────────────────────────────────────────────────────
# 6. Step Endpoint (Task 3: Reply)
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[6/11] Step Endpoint - Task 3 (Reply)${NC}"
STEP3=$(curl -sf -X POST "$PING_URL/openenv/step" \
  -H "Content-Type: application/json" \
  -d '{"action":{"task_id":3,"action_type":"reply","reply_text":"Thank you for your email. I confirm the deadline and deliverables."}}' \
  --max-time 30 2>/dev/null)
REWARD3=$(echo "$STEP3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reward',''))" 2>/dev/null)
DONE=$(echo "$STEP3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('done',''))" 2>/dev/null)
if [ "$REWARD3" != "" ] && [ "$DONE" = "True" ]; then
  pass_check "Task 3: reward=$REWARD3, episode complete"
else
  fail_check "Task 3: invalid response (reward=$REWARD3, done=$DONE)"
fi

# ──────────────────────────────────────────────────────────────
# 7. Scores in 0.0-1.0 Range
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[7/11] Scores in Valid Range (0.0-1.0)${NC}"
SCORES_OK=true
for r in "$REWARD1" "$REWARD2" "$REWARD3"; do
  VALID=$(python3 -c "r=float('$r'); print('yes' if 0.0 <= r <= 1.0 else 'no')" 2>/dev/null)
  if [ "$VALID" != "yes" ]; then
    SCORES_OK=false
  fi
done
if [ "$SCORES_OK" = true ]; then
  pass_check "All rewards in [0.0, 1.0]: $REWARD1, $REWARD2, $REWARD3"
else
  fail_check "Some rewards outside [0.0, 1.0] range"
fi

# ──────────────────────────────────────────────────────────────
# 8. openenv.yaml Present
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[8/11] openenv.yaml Present${NC}"
if [ -f "$REPO_DIR/openenv.yaml" ]; then
  if python3 -c "
import yaml, sys
with open('$REPO_DIR/openenv.yaml') as f:
    d = yaml.safe_load(f)
assert 'name' in d, 'missing name'
assert 'sdk' in d, 'missing sdk'
assert d['sdk'] == 'docker', 'sdk must be docker'
print('valid')
" 2>/dev/null | grep -q "valid"; then
    pass_check "openenv.yaml exists with required fields (name, sdk=docker)"
  else
    fail_check "openenv.yaml exists but missing required fields"
  fi
else
  fail_check "openenv.yaml not found in repo root"
fi

# ──────────────────────────────────────────────────────────────
# 9. inference.py in Root + Required Env Vars
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[9/11] inference.py + Required Env Vars${NC}"
if [ -f "$REPO_DIR/inference.py" ]; then
  pass_check "inference.py found in root directory"

  # Check required env vars
  MISSING=""
  for var in "API_BASE_URL" "MODEL_NAME" "HF_TOKEN"; do
    if ! grep -q "os.getenv(\"$var\"\|os.getenv('$var'" "$REPO_DIR/inference.py" 2>/dev/null; then
      MISSING="$MISSING $var"
    fi
  done
  if [ -z "$MISSING" ]; then
    pass_check "All required env vars defined: API_BASE_URL, MODEL_NAME, HF_TOKEN"
  else
    fail_check "Missing env vars:$MISSING"
  fi
else
  fail_check "inference.py not found in root directory"
fi

# ──────────────────────────────────────────────────────────────
# 10. OpenAI Client Usage + STDOUT Format
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[10/11] OpenAI Client + STDOUT Format${NC}"
if grep -q "from openai import OpenAI" "$REPO_DIR/inference.py" 2>/dev/null; then
  pass_check "Uses OpenAI Client (from openai import OpenAI)"
else
  fail_check "Missing: from openai import OpenAI"
fi

if grep -q "\[START\]" "$REPO_DIR/inference.py" 2>/dev/null && \
   grep -q "\[STEP\]"  "$REPO_DIR/inference.py" 2>/dev/null && \
   grep -q "\[END\]"   "$REPO_DIR/inference.py" 2>/dev/null; then
  pass_check "STDOUT format includes [START], [STEP], [END]"
else
  fail_check "Missing [START]/[STEP]/[END] in stdout format"
fi

# ──────────────────────────────────────────────────────────────
# 11. Docker Build (Optional — 600s timeout)
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}[11/11] Docker Build (Optional)${NC}"
if [ -f "$REPO_DIR/Dockerfile" ]; then
  if command -v docker &>/dev/null; then
    echo "  Building Docker image (timeout: ${DOCKER_BUILD_TIMEOUT}s)..."
    if run_with_timeout $DOCKER_BUILD_TIMEOUT docker build -t email-triage-validate "$REPO_DIR" >/dev/null 2>&1; then
      pass_check "Docker build succeeded"
      docker rmi email-triage-validate >/dev/null 2>&1
    else
      warn_check "Docker build failed or timed out"
    fi
  else
    warn_check "Docker not installed — skipping build test"
  fi
else
  fail_check "Dockerfile not found"
fi

# ──────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN))
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  📊  VALIDATION SUMMARY                                 ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo -e "║  ✅  Passed : ${GREEN}$PASS${NC}                                            ║"
echo -e "║  ❌  Failed : ${RED}$FAIL${NC}                                            ║"
echo -e "║  ⚠️  Warnings: ${YELLOW}$WARN${NC}                                            ║"
echo -e "║  📋  Total  : $TOTAL                                            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}🎉  ALL CHECKS PASSED — Ready to submit!${NC}"
  echo ""
  exit 0
else
  echo -e "${RED}${BOLD}❌  $FAIL check(s) failed — fix before submitting${NC}"
  echo ""
  exit 1
fi
