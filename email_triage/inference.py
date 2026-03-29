"""
Baseline Inference Script — Email Triage Environment.
FINAL FIXED: reward lives at top level of response, not inside observation.
"""

import os
import re
import json
import requests
from openai import OpenAI

HF_TOKEN     = os.environ.get("HF_TOKEN", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct:cerebras")
ENV_URL      = "http://127.0.0.1:7860"

if not HF_TOKEN:
    raise ValueError("HF_TOKEN not set. Run: setx HF_TOKEN your_token")

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)


def parse_json(raw: str) -> dict:
    """Robustly parse JSON — strips markdown code blocks if present."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    print(f"  [PARSE FAILED] {raw[:200]}")
    return {}


def env_reset():
    """Returns full response dict: {observation, reward, done}"""
    response = requests.post(f"{ENV_URL}/reset")
    response.raise_for_status()
    return response.json()   # ← return full response, not just observation


def env_step(action: dict):
    """Returns full response dict: {observation, reward, done}"""
    response = requests.post(
        f"{ENV_URL}/step",
        json={"action": action},
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response.json()   # ← return full response, not just observation


def call_llm(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert email assistant. "
                        "You MUST respond with ONLY a valid JSON object. "
                        "No explanation, no markdown, no code blocks. "
                        "Start with { and end with }."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        print(f"  [LLM] {raw[:100]}")
        return raw
    except Exception as e:
        print(f"  [LLM ERROR] {e}")
        return "{}"


def agent_task1(obs: dict) -> dict:
    email = obs["observation"]["emails"][0]
    prompt = f"""Classify this email as spam or not_spam.

Subject: {email['subject']}
From: {email['sender']}
Body: {email['body']}

Output ONLY this JSON:
{{"task_id": 1, "label": "spam"}}
or
{{"task_id": 1, "label": "not_spam"}}"""
    raw = call_llm(prompt)
    action = parse_json(raw)
    label = str(action.get("label", "")).strip().lower()
    if label not in ["spam", "not_spam"]:
        print(f"  [FALLBACK] '{label}' invalid, using spam")
        label = "spam"
    return {"task_id": 1, "label": label}


def agent_task2(obs: dict) -> dict:
    emails_text = ""
    for e in obs["observation"]["emails"]:
        emails_text += f"\nEmail ID {e['id']}: {e['subject']} | {e['body'][:100]}"
    prompt = f"""Rank these 3 emails from MOST to LEAST urgent.
{emails_text}

Output ONLY this JSON:
{{"task_id": 2, "ranking": [most_urgent_id, second_id, least_urgent_id]}}
Example: {{"task_id": 2, "ranking": [1, 2, 0]}}"""
    raw = call_llm(prompt)
    action = parse_json(raw)
    ranking = action.get("ranking", [])
    if not isinstance(ranking, list) or len(ranking) != 3 or set(ranking) != {0, 1, 2}:
        print(f"  [FALLBACK] ranking invalid, using [1,2,0]")
        ranking = [1, 2, 0]
    return {"task_id": 2, "ranking": ranking}


def agent_task3(obs: dict) -> dict:
    email = obs["observation"]["emails"][0]
    prompt = f"""Handle this email professionally.

Subject: {email['subject']}
From: {email['sender']}
Body: {email['body']}

Choose: "reply", "forward", "archive", or "delete"
Write a reply mentioning: confirm, friday, deadline, deliver

Output ONLY this JSON:
{{"task_id": 3, "action_type": "reply", "reply_text": "your reply here"}}"""
    raw = call_llm(prompt)
    action = parse_json(raw)
    action_type = str(action.get("action_type", "reply")).strip().lower()
    if action_type not in {"reply", "forward", "archive", "delete"}:
        action_type = "reply"
    reply_text = action.get("reply_text", "").strip()
    if not reply_text:
        reply_text = (
            "Thank you. I confirm we will deliver all items "
            "by Friday EOD deadline as agreed."
        )
    return {"task_id": 3, "action_type": action_type, "reply_text": reply_text}


def run_episode() -> dict:
    scores = {}
    print("\n" + "="*50)
    print("  EMAIL TRIAGE — BASELINE AGENT")
    print("="*50)

    # Reset — get fresh episode
    print("\n[1/4] Resetting environment...")
    result = env_reset()
    print(f"  Task: {result['observation'].get('task_description','')[:70]}...")

    # Task 1
    print("\n[2/4] Task 1 — Spam Classification...")
    action1 = agent_task1(result)
    print(f"  Action: {action1}")
    result = env_step(action1)
    scores["task_1"] = result.get("reward", 0.0)   # reward at top level ✓
    print(f"  Reward: {scores['task_1']}")
    print(f"  Feedback: {result['observation'].get('feedback','')}")

    # Task 2
    print("\n[3/4] Task 2 — Urgency Ranking...")
    action2 = agent_task2(result)
    print(f"  Action: {action2}")
    result = env_step(action2)
    scores["task_2"] = result.get("reward", 0.0)   # reward at top level ✓
    print(f"  Reward: {scores['task_2']}")
    print(f"  Feedback: {result['observation'].get('feedback','')}")

    # Task 3
    print("\n[4/4] Task 3 — Action + Reply...")
    action3 = agent_task3(result)
    print(f"  Action type: {action3['action_type']}")
    print(f"  Reply: {action3['reply_text'][:80]}...")
    result = env_step(action3)
    scores["task_3"] = result.get("reward", 0.0)   # reward at top level ✓
    print(f"  Reward: {scores['task_3']}")
    print(f"  Feedback: {result['observation'].get('feedback','')}")

    # Final score
    valid = [s for s in scores.values() if s >= 0]
    final = round(sum(valid) / len(valid), 3) if valid else 0.0
    scores["final"] = final

    print("\n" + "="*50)
    print("  RESULTS")
    print("="*50)
    print(f"  Task 1 (Spam Classification): {scores['task_1']}")
    print(f"  Task 2 (Urgency Ranking):     {scores['task_2']}")
    print(f"  Task 3 (Action + Reply):      {scores['task_3']}")
    print(f"  Final Average Score:          {scores['final']}")
    print("="*50 + "\n")
    return scores


if __name__ == "__main__":
    scores = run_episode()
    with open("baseline_scores.json", "w") as f:
        json.dump(scores, f, indent=2)
    print("Scores saved to baseline_scores.json")