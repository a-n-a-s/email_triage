"""
Email Triage - Competition Inference Script
============================================
MANDATORY SUBMISSION SCRIPT

This script runs baseline inference for the Email Triage environment.
It emits structured stdout logs in the required competition format.

MANDATORY
- Before submitting, ensure the following variables are defined in your environment:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    LOCAL_IMAGE_NAME The name of the local image if using from_docker_image().

- Defaults are set only for API_BASE_URL and MODEL_NAME:
    API_BASE_URL = os.getenv("API_BASE_URL", "<your-active-endpoint>")
    MODEL_NAME = os.getenv("MODEL_NAME", "<your-active-model>")

- HF_TOKEN has no default — must be provided by the user.

- The inference script must be named `inference.py` and placed in the root directory
- Participants must use OpenAI Client for all LLM calls using above variables

- Participants must emit structured stdout logs strictly following the
  [START], [STEP], and [END] format:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Example:
    [START] task=spam-classification env=email-triage model=llama3.2
    [STEP] step=1 action={"task_id":1,"label":"spam"} reward=1.00 done=false error=null
    [STEP] step=2 action={"task_id":2,"ranking":[1,2,0]} reward=0.60 done=false error=null
    [STEP] step=3 action={"task_id":3,"action_type":"reply","reply_text":"..."} reward=0.80 done=true error=null
    [END] success=true steps=3 score=0.80 rewards=1.00,0.60,0.80
"""

import os
import re
import json
import time
import sys
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict

# Use OpenAI Client for all LLM calls (MANDATORY)
try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package is required. Install with: pip install openai")
    sys.exit(1)

import requests

# ============================================================================
# MANDATORY ENVIRONMENT VARIABLES
# ============================================================================

# Defaults are set only for API_BASE_URL and MODEL_NAME
# HF_TOKEN has NO default — must be provided by user
API_BASE_URL = os.getenv("API_BASE_URL", "<your-active-endpoint>")
MODEL_NAME = os.getenv("MODEL_NAME", "<your-active-model>")
HF_TOKEN = os.getenv("HF_TOKEN")

# Optional — if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# Environment Configuration
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
MAX_STEPS = 10
NUM_EPISODES = int(os.getenv("NUM_EPISODES", "3"))

# LLM Configuration
TEMPERATURE = 0.2
MAX_TOKENS = 500

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 2.0

# Output Configuration
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SAVE_RESULTS = True
RESULTS_FILE = "inference_results.json"
LOG_FILE = "inference_log.txt"

# Setup logging (to stderr so stdout is clean for competition format)
# Force UTF-8 encoding for Windows console compatibility
if sys.platform == "win32":
    import io
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# COMPETITION FORMAT HELPERS
# ============================================================================

def emit_start(task_name: str, env: str, model: str):
    """Emit [START] line to stdout."""
    print(f"[START] task={task_name} env={env} model={model}", flush=True)


def emit_step(step_num: int, action_str: str, reward: float, done: bool, error: Optional[str] = None):
    """Emit [STEP] line to stdout."""
    error_str = error if error else "null"
    done_str = "true" if done else "false"
    # Escape any newlines in action_str
    action_str = action_str.replace('\n', ' ').replace('\r', '')
    print(f"[STEP] step={step_num} action={action_str} reward={reward:.2f} done={done_str} error={error_str}", flush=True)


def emit_end(success: bool, steps: int, score: float, rewards: List[float]):
    """Emit [END] line to stdout."""
    success_str = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={success_str} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TokenUsage:
    """Track token usage and costs."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add(self, input_tokens: int, output_tokens: int):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EpisodeResult:
    """Store episode results."""
    episode_num: int
    timestamp: str
    model: str
    task_name: str
    rewards: List[float] = field(default_factory=list)
    steps: int = 0
    success: bool = False
    score: float = 0.0
    tokens: TokenUsage = field(default_factory=TokenUsage)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['tokens'] = self.tokens.to_dict()
        return result


# ============================================================================
# LLM AGENT
# ============================================================================

class EmailTriageAgent:
    """LLM-powered agent for email triage tasks using OpenAI Client."""

    # Task names for competition output
    TASK_NAMES = {
        1: "spam-classification",
        2: "urgency-ranking",
        3: "action-reply"
    }

    # Few-shot examples for each task
    FEW_SHOT_EXAMPLES = {
        1: [
            {
                "email": {"subject": "You WON $1000! Claim NOW!", "sender": "prizes@scam.biz", "body": "Click here immediately!"},
                "label": "spam",
            },
            {
                "email": {"subject": "Team standup at 10am", "sender": "manager@company.com", "body": "Daily sync meeting."},
                "label": "not_spam",
            }
        ],
        2: [
            {
                "emails": [
                    {"id": 0, "subject": "Newsletter: Top 10 tips"},
                    {"id": 1, "subject": "CRITICAL: Server down"},
                    {"id": 2, "subject": "Invoice due in 3 days"}
                ],
                "ranking": [1, 2, 0],
            }
        ],
        3: [
            {
                "email": {"subject": "Project deadline", "sender": "client@company.com", "body": "Can you confirm delivery by Friday?"},
                "action_type": "reply",
                "reply_text": "Thank you for your email. I confirm that we will deliver by Friday EOD as agreed.",
            }
        ]
    }

    def __init__(self, api_base: str, api_key: str, model: str,
                 temperature: float = 0.2):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.tokens = TokenUsage()
        self.client = OpenAI(base_url=api_base, api_key=api_key)

    def _build_prompt(self, task_id: int, task_description: str,
                      emails: List[Dict]) -> str:
        """Build prompt with few-shot examples."""
        # Format emails
        email_context = ""
        for i, email in enumerate(emails):
            email_context += f"""
--- Email {i} ---
From: {email.get('sender', 'Unknown')}
Subject: {email.get('subject', 'No subject')}
Body: {email.get('body', '')}
"""

        # Build task-specific prompt
        if task_id == 1:
            examples = self.FEW_SHOT_EXAMPLES[1]
            examples_text = "\n".join([
                f"Example {j+1}: Label={ex['label']}, Email: {ex['email']['subject']}"
                for j, ex in enumerate(examples)
            ])

            prompt = f"""You are an AI assistant helping triage emails.

{examples_text}

{email_context}
TASK: Spam Classification
Classify the email above as either 'spam' or 'not_spam'.

CRITICAL: Respond with ONLY valid JSON. No explanations, no comments, no markdown.

{{"label": "spam" or "not_spam"}}
"""

        elif task_id == 2:
            examples = self.FEW_SHOT_EXAMPLES[2]
            examples_text = "\n".join([
                f"Example {j+1}: Ranking={ex['ranking']}, Emails: {len(ex['emails'])}"
                for j, ex in enumerate(examples)
            ])

            prompt = f"""You are an AI assistant helping triage emails by urgency.

{examples_text}

{email_context}
TASK: Urgency Ranking
Rank the 3 emails above by urgency from MOST urgent to LEAST urgent.

CRITICAL: Respond with ONLY valid JSON. No explanations, no comments, no markdown.
Use the email IDs (0, 1, or 2) in order from most urgent to least urgent.

{{"ranking": [most_urgent_id, second_urgent_id, least_urgent_id]}}
"""

        elif task_id == 3:
            examples = self.FEW_SHOT_EXAMPLES[3]
            examples_text = "\n".join([
                f"Example {j+1}: Action={ex['action_type']}, Reply: {ex['reply_text'][:50]}..."
                for j, ex in enumerate(examples)
            ])

            prompt = f"""You are an AI assistant helping triage emails and compose replies.

{examples_text}

{email_context}
TASK: Action & Reply
Decide what action to take and write a reply if needed.

Action Guidelines:
- 'reply': Email requires a response
- 'forward': Email needs attention from someone else
- 'archive': Important but no action needed
- 'delete': Spam or irrelevant emails

CRITICAL: Respond with ONLY valid JSON. No explanations, no comments, no markdown.
Keep reply_text professional and concise (under 200 characters).

{{"action_type": "reply/forward/archive/delete", "reply_text": "your professional reply"}}
"""
        else:
            prompt = f"TASK: {task_description}\n\n{email_context}"

        return prompt

    def step(self, task_id: int, task_description: str,
             emails: List[Dict]) -> Tuple[Dict[str, Any], int]:
        """
        Get action from LLM.

        Returns:
            Tuple of (action_dict, tokens_used)
        """
        prompt = self._build_prompt(task_id, task_description, emails)

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful email triage assistant. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=MAX_TOKENS
                )
                response_text = response.choices[0].message.content.strip()
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0
                tokens_used = response.usage.total_tokens if response.usage else 0

                self.tokens.add(input_tokens, output_tokens)

                logger.debug(f"LLM Response: {response_text[:200]}...")

                action = self._parse_response(response_text, task_id)
                logger.debug(f"Parsed Action: {action}")

                return action, tokens_used

            except Exception as e:
                error_str = str(e)
                # Handle 429 rate limits with exponential backoff
                if "429" in error_str or "rate" in error_str.lower():
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                elif attempt < MAX_RETRIES - 1:
                    logger.warning(f"LLM Error (attempt {attempt+1}/{MAX_RETRIES}): {e}")
                    time.sleep(1)
                else:
                    logger.error(f"LLM Error after {MAX_RETRIES} attempts: {e}")
                    return self._get_fallback_action(task_id), 0

        return self._get_fallback_action(task_id), 0

    def _parse_response(self, response_text: str, task_id: int) -> Dict[str, Any]:
        """Parse LLM response into action dict."""
        # Strip markdown code blocks (```json ... ```)
        response_text = re.sub(r'```(?:json)?\s*', '', response_text)
        response_text = re.sub(r'```', '', response_text)

        # Find first { and last } to capture complete JSON object
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            response_text = response_text[start:end + 1]
            # Remove // comments that break JSON parsing
            response_text = re.sub(r'//[^\n]*', '', response_text)

        try:
            action = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {response_text[:200]}... Error: {e}")
            return self._get_fallback_action(task_id)

        # Validate and normalize action based on task
        if task_id == 1:
            label = action.get("label", "").lower().strip()
            if label not in ["spam", "not_spam"]:
                logger.warning(f"Invalid label '{label}', defaulting to 'spam'")
                label = "spam"
            return {"task_id": task_id, "label": label}

        elif task_id == 2:
            ranking = action.get("ranking", [])
            if not isinstance(ranking, list) or len(ranking) != 3:
                logger.warning(f"Invalid ranking {ranking}, defaulting to [1, 2, 0]")
                ranking = [1, 2, 0]
            if set(ranking) != {0, 1, 2}:
                logger.warning(f"Invalid ranking IDs {ranking}, defaulting to [1, 2, 0]")
                ranking = [1, 2, 0]
            return {"task_id": task_id, "ranking": ranking}

        elif task_id == 3:
            action_type = action.get("action_type", "reply").lower().strip()
            if action_type not in ["reply", "forward", "archive", "delete"]:
                logger.warning(f"Invalid action_type '{action_type}', defaulting to 'reply'")
                action_type = "reply"
            reply_text = action.get("reply_text", "")
            if action_type == "reply" and not reply_text:
                reply_text = "Thank you for your email. I will review and respond accordingly."
            return {
                "task_id": task_id,
                "action_type": action_type,
                "reply_text": reply_text
            }

        return action

    def _get_fallback_action(self, task_id: int) -> Dict[str, Any]:
        """Return safe fallback action."""
        if task_id == 1:
            return {"task_id": task_id, "label": "spam"}
        elif task_id == 2:
            return {"task_id": task_id, "ranking": [1, 2, 0]}
        elif task_id == 3:
            return {
                "task_id": task_id,
                "action_type": "reply",
                "reply_text": "Thank you for your email. I will review this and get back to you."
            }
        return {}


# ============================================================================
# ENVIRONMENT CLIENT
# ============================================================================

class EnvClient:
    """HTTP client for the Email Triage environment."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.session = requests.Session()
        self.timeout = timeout

    def reset(self) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/openenv/reset",
            json={},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/openenv/step",
            json={"action": action},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def health(self) -> Dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/health",
            timeout=10
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# MAIN INFERENCE LOOP (COMPETITION FORMAT)
# ============================================================================

def run_episode(agent: EmailTriageAgent, env: EnvClient,
                episode_num: int = 0) -> EpisodeResult:
    """
    Run a complete episode with competition-compliant stdout format.

    Emits:
        [START] task=<task_name> env=email-triage model=<model_name>
        [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
        [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
    """
    start_time = time.time()
    rewards_list = []
    step_count = 0
    done = False
    error = None

    # Reset environment
    try:
        obs_data = env.reset()
        observation = obs_data.get("observation", {})
    except Exception as e:
        logger.error(f"Failed to reset environment: {e}")
        emit_start("email-triage", "email-triage", agent.model)
        emit_end(False, 0, 0.0, [])
        return EpisodeResult(
            episode_num=episode_num,
            timestamp=datetime.now().isoformat(),
            model=agent.model,
            task_name="email-triage",
            success=False,
            score=0.0
        )

    task_id = observation.get("task_id", 1)
    task_description = observation.get("task_description", "")
    emails = observation.get("emails", [])

    # Map task ID to name for competition output
    task_name_map = {1: "spam-classification", 2: "urgency-ranking", 3: "action-reply"}
    task_name = task_name_map.get(task_id, f"task-{task_id}")

    # Emit [START] line
    emit_start(task_name, "email-triage", agent.model)

    logger.info(f"  📋  Task {task_id}: {task_description[:60]}...")
    logger.info(f"  📬  Emails  : {len(emails)} to process")
    logger.info("")

    while not done and step_count < MAX_STEPS:
        step_count += 1

        # Get action from agent
        try:
            action, tokens = agent.step(task_id, task_description, emails)
        except Exception as e:
            error = str(e)
            logger.error(f"Agent step failed: {e}")
            action = agent._get_fallback_action(task_id)

        # Format action string for output
        action_str = json.dumps(action, separators=(',', ':'))

        # Execute action in environment
        try:
            step_response = env.step(action)
            error = None
        except Exception as e:
            error = str(e)
            logger.error(f"Environment step failed: {e}")
            step_response = {"reward": 0.0, "done": False, "observation": {}}

        # Parse result
        reward = step_response.get("reward", 0.0)
        done = step_response.get("done", False)
        new_obs = step_response.get("observation", {})

        rewards_list.append(reward)

        # Emit [STEP] line
        emit_step(step_count, action_str, reward, done, error)

        # Emoji feedback for each step
        if reward >= 0.8:
            emoji = "🟢"
        elif reward >= 0.5:
            emoji = "🟡"
        else:
            emoji = "🔴"

        logger.info(f"  {emoji}  Step {step_count}  →  Reward: {reward:.2f}  |  Done: {done}")

        if not done:
            task_id = new_obs.get("task_id", task_id + 1)
            task_description = new_obs.get("task_description", "")
            emails = new_obs.get("emails", [])
            task_name = task_name_map.get(task_id, f"task-{task_id}")

    # Calculate final score (average of all rewards)
    score = sum(rewards_list) / len(rewards_list) if rewards_list else 0.0
    success = done

    elapsed = time.time() - start_time

    # Emit [END] line
    emit_end(success, step_count, score, rewards_list)

    # Episode summary
    if score >= 0.8:
        grade = "🏆  Excellent"
    elif score >= 0.6:
        grade = "👍  Good"
    elif score >= 0.4:
        grade = "⚠️   Fair"
    else:
        grade = "❌  Poor"

    logger.info(f"  📝  Episode Summary:")
    logger.info(f"      Steps   : {step_count}")
    logger.info(f"      Score   : {score:.2f}  {grade}")
    logger.info(f"      Rewards : {', '.join(f'{r:.2f}' for r in rewards_list)}")
    logger.info(f"      Time    : {elapsed:.1f}s")

    return EpisodeResult(
        episode_num=episode_num,
        timestamp=datetime.now().isoformat(),
        model=agent.model,
        task_name=task_name,
        rewards=rewards_list,
        steps=step_count,
        success=success,
        score=score,
        tokens=agent.tokens,
        duration_seconds=elapsed
    )


def main():
    """Main inference function."""
    import argparse

    parser = argparse.ArgumentParser(description='Email Triage Inference Script')
    parser.add_argument('--episodes', type=int, default=NUM_EPISODES, help='Number of episodes')
    args = parser.parse_args()

    num_episodes = args.episodes

    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║  📧  EMAIL TRIAGE — COMPETITION INFERENCE               ║")
    logger.info("╠══════════════════════════════════════════════════════════╣")
    logger.info(f"║  🌐  API URL   : {API_BASE_URL:<42} ║")
    logger.info(f"║  🤖  Model     : {MODEL_NAME:<42} ║")
    logger.info(f"║  🖥️  Environment: {ENV_BASE_URL:<42} ║")
    logger.info(f"║  📊  Episodes  : {num_episodes:<42} ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("")

    # Validate environment
    if not HF_TOKEN:
        logger.error("❌  ERROR: HF_TOKEN not set")
        logger.error("    Set: export HF_TOKEN='your_token'")
        return

    # Initialize agent
    agent = EmailTriageAgent(
        api_base=API_BASE_URL,
        api_key=HF_TOKEN,
        model=MODEL_NAME,
        temperature=TEMPERATURE
    )

    env = EnvClient(base_url=ENV_BASE_URL)

    # Check environment health
    logger.info("🏥  Checking environment health...")
    try:
        health = env.health()
        logger.info("✅  Environment is healthy and ready!\n")
    except Exception as e:
        logger.error(f"❌  Environment not responding: {e}")
        logger.error(f"    Make sure the server is running at {ENV_BASE_URL}")
        return

    # Run episodes
    all_results = []
    start_time = time.time()

    for ep in range(num_episodes):
        logger.info("━" * 60)
        logger.info(f"🎮  EPISODE {ep + 1} / {num_episodes}")
        logger.info("━" * 60)
        result = run_episode(agent, env, ep)
        all_results.append(result)
        logger.info("")

    # Calculate overall statistics
    elapsed = time.time() - start_time

    if num_episodes > 1:
        avg_score = sum(r.score for r in all_results) / len(all_results)
        completion_rate = sum(1 for r in all_results if r.success) / len(all_results)

        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║  📊  OVERALL RESULTS                                    ║")
        logger.info("╠══════════════════════════════════════════════════════════╣")
        logger.info(f"║  📈  Episodes        : {num_episodes:<34} ║")
        logger.info(f"║  ⭐  Avg Score        : {avg_score:.3f}{' ' * 36}║")
        logger.info(f"║  ✅  Completion Rate  : {completion_rate:.1%}{' ' * 34}║")
        logger.info(f"║  🪙  Total Tokens     : {agent.tokens.total_tokens:<34} ║")
        logger.info(f"║  ⏱️   Total Time       : {elapsed:.1f}s{' ' * 37}║")
        logger.info("╚══════════════════════════════════════════════════════════╝")
        logger.info("")

    # Save results
    if SAVE_RESULTS:
        output = {
            "config": {
                "model": MODEL_NAME,
                "api_base": API_BASE_URL,
                "env_base": ENV_BASE_URL,
                "temperature": TEMPERATURE,
                "num_episodes": num_episodes
            },
            "episodes": [r.to_dict() for r in all_results],
            "summary": {
                "num_episodes": num_episodes,
                "avg_score": sum(r.score for r in all_results) / len(all_results) if all_results else 0,
                "completion_rate": sum(1 for r in all_results if r.success) / len(all_results) if all_results else 0,
                "total_tokens": agent.tokens.total_tokens,
                "total_time_seconds": elapsed
            }
        }

        with open(RESULTS_FILE, "w", encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"💾  Results saved to {RESULTS_FILE}")
        logger.info("")

    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║  ✅  INFERENCE COMPLETE                                 ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("")


if __name__ == "__main__":
    main()
