# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Email Triage Environment — Full Hackathon Implementation.

Uses CLASS-LEVEL state so all HTTP requests share the same episode state.
This is required because create_app instantiates a new object per request.
"""

from uuid import uuid4
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import EmailTriageAction, EmailTriageObservation
except ImportError:
    from models import EmailTriageAction, EmailTriageObservation


# ─────────────────────────────────────────────
# SAMPLE EMAIL DATA
# ─────────────────────────────────────────────

TASK1_EMAILS = [
    {
        "id": 0,
        "subject": "You WON a $1000 gift card! Click NOW!",
        "sender": "prizes@totallyreal.biz",
        "body": "Congratulations! You have been selected. Click the link to claim your reward immediately!",
        "correct_label": "spam",
    },
    {
        "id": 1,
        "subject": "Team standup moved to 3pm today",
        "sender": "manager@company.com",
        "body": "Hi team, just a heads up — today's standup is moved from 2pm to 3pm. Same link.",
        "correct_label": "not_spam",
    },
    {
        "id": 2,
        "subject": "URGENT: Your account will be suspended",
        "sender": "support@bank-secure-alert.net",
        "body": "Dear customer, verify your details immediately or your account will be suspended within 24 hours.",
        "correct_label": "spam",
    },
]

TASK2_EMAILS = [
    {
        "id": 0,
        "subject": "Newsletter: Top 10 productivity tips",
        "sender": "newsletter@tips.io",
        "body": "Here are this week's top productivity tips for remote workers...",
        "urgency": 3,
    },
    {
        "id": 1,
        "subject": "URGENT: Production server is down",
        "sender": "alerts@monitoring.company.com",
        "body": "CRITICAL: The main production server has been unreachable for 5 minutes. Immediate action required.",
        "urgency": 1,
    },
    {
        "id": 2,
        "subject": "Your invoice is due in 3 days",
        "sender": "billing@vendor.com",
        "body": "This is a reminder that invoice #4521 for $340 is due on Friday.",
        "urgency": 2,
    },
]
TASK2_CORRECT_RANKING = [1, 2, 0]

TASK3_EMAIL = {
    "id": 0,
    "subject": "Re: Project deadline extension request",
    "sender": "client@bigcorp.com",
    "body": (
        "Hi, we've reviewed the project timeline and unfortunately we cannot "
        "extend the deadline. We need the deliverables by Friday EOD as originally "
        "agreed. Please confirm you can meet this deadline or escalate immediately."
    ),
    "correct_action": "reply",
    "required_keywords": ["confirm", "friday", "deadline", "deliver"],
}


# ─────────────────────────────────────────────
# GRADERS
# ─────────────────────────────────────────────

def grade_task1(action: EmailTriageAction, email_index: int) -> tuple[float, str]:
    correct = TASK1_EMAILS[email_index]["correct_label"]
    given = (action.label or "").strip().lower()
    if given not in {"spam", "not_spam"}:
        return -0.2, f"Invalid label '{given}'. Must be 'spam' or 'not_spam'."
    if given == correct:
        return 1.0, f"Correct! This email is '{correct}'."
    return 0.0, f"Wrong. Expected '{correct}', got '{given}'."


def grade_task2(action: EmailTriageAction) -> tuple[float, str]:
    ranking = action.ranking
    if not ranking or len(ranking) != 3:
        return -0.2, "Invalid ranking. Provide a list of 3 email indices."
    if set(ranking) != {0, 1, 2}:
        return -0.2, "Ranking must contain exactly indices 0, 1, and 2."
    correct = TASK2_CORRECT_RANKING
    matches = sum(1 for i, v in enumerate(ranking) if v == correct[i])
    if matches == 3:
        return 1.0, "Perfect ranking!"
    elif matches == 2:
        return 0.6, f"Almost! 2/3 correct. Correct order: {correct}."
    elif matches == 1:
        return 0.3, f"1/3 correct. Correct order: {correct}."
    return 0.0, f"Incorrect. Correct order: {correct}."


def grade_task3(action: EmailTriageAction) -> tuple[float, str]:
    correct_action = TASK3_EMAIL["correct_action"]
    required_keywords = TASK3_EMAIL["required_keywords"]
    given_action = (action.action_type or "").strip().lower()
    reply = (action.reply_text or "").strip().lower()
    if given_action not in {"reply", "forward", "archive", "delete"}:
        return -0.2, f"Invalid action '{given_action}'."
    action_score = 0.5 if given_action == correct_action else 0.0
    action_feedback = "correct action" if action_score else f"wrong action (expected '{correct_action}')"
    if not reply:
        reply_score, reply_feedback = 0.0, "no reply written"
    else:
        found = [kw for kw in required_keywords if kw in reply]
        reply_score = round((len(found) / len(required_keywords)) * 0.5, 2)
        reply_feedback = f"reply covered {len(found)}/{len(required_keywords)} key topics"
    total = round(action_score + reply_score, 2)
    return total, f"Score {total}/1.0 — {action_feedback}, {reply_feedback}."


# ─────────────────────────────────────────────
# SHARED STATE — class level so all HTTP
# requests see the same episode state
# ─────────────────────────────────────────────

class _SharedState:
    episode_id: str = str(uuid4())
    step_count: int = 0
    current_task: int = 1
    task1_email_index: int = 0
    scores: list = []
    done: bool = False

    @classmethod
    def reset(cls):
        cls.episode_id = str(uuid4())
        cls.step_count = 0
        cls.current_task = 1
        cls.task1_email_index = 0
        cls.scores = []
        cls.done = False


# ─────────────────────────────────────────────
# ENVIRONMENT
# ─────────────────────────────────────────────

class EmailTriageEnvironment(Environment):
    """
    Email Triage Environment.
    Uses class-level _SharedState so all HTTP requests share episode state.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        # Instance state just wraps shared state
        pass

    @property
    def state(self) -> State:
        return State(
            episode_id=_SharedState.episode_id,
            step_count=_SharedState.step_count,
        )

    def reset(self) -> EmailTriageObservation:
        _SharedState.reset()
        email = TASK1_EMAILS[_SharedState.task1_email_index]
        return EmailTriageObservation(
            task_id=1,
            task_description=(
                "TASK 1 (Easy) — Spam Classification: "
                "Read the email below and classify it as 'spam' or 'not_spam'. "
                "Set action.label to your answer."
            ),
            emails=[{
                "id": email["id"],
                "subject": email["subject"],
                "sender": email["sender"],
                "body": email["body"],
            }],
            reward=0.0,
            done=False,
            feedback="Episode started. Classify the email as 'spam' or 'not_spam'.",
        )

    def step(self, action: EmailTriageAction) -> EmailTriageObservation:
        if _SharedState.done:
            return EmailTriageObservation(
                task_id=_SharedState.current_task,
                task_description="Episode complete. Call reset() to start again.",
                emails=[],
                reward=0.0,
                done=True,
                feedback="Episode already finished.",
            )

        _SharedState.step_count += 1

        # ── TASK 1 ──
        if _SharedState.current_task == 1:
            score, feedback = grade_task1(action, _SharedState.task1_email_index)
            if score == 1.0 and _SharedState.step_count == 1:
                score = min(1.0, score + 0.1)
                feedback += " (+0.1 efficiency bonus)"
            _SharedState.scores.append(score)
            _SharedState.current_task = 2

            return EmailTriageObservation(
                task_id=2,
                task_description=(
                    "TASK 2 (Medium) — Urgency Ranking: "
                    "Rank the 3 emails below by urgency. "
                    "Set action.ranking to a list of email IDs from MOST to LEAST urgent. "
                    "Example: [1, 2, 0] means email 1 is most urgent."
                ),
                emails=[{
                    "id": e["id"], "subject": e["subject"],
                    "sender": e["sender"], "body": e["body"],
                } for e in TASK2_EMAILS],
                reward=score,
                done=False,
                feedback=f"Task 1 result: {feedback} Moving to Task 2.",
            )

        # ── TASK 2 ──
        elif _SharedState.current_task == 2:
            score, feedback = grade_task2(action)
            _SharedState.scores.append(score)
            _SharedState.current_task = 3

            return EmailTriageObservation(
                task_id=3,
                task_description=(
                    "TASK 3 (Hard) — Action + Reply: "
                    "Read the email and set action.action_type to one of: "
                    "'reply', 'forward', 'archive', 'delete'. "
                    "Also write a professional reply in action.reply_text."
                ),
                emails=[{
                    "id": TASK3_EMAIL["id"],
                    "subject": TASK3_EMAIL["subject"],
                    "sender": TASK3_EMAIL["sender"],
                    "body": TASK3_EMAIL["body"],
                }],
                reward=score,
                done=False,
                feedback=f"Task 2 result: {feedback} Moving to Task 3.",
            )

        # ── TASK 3 ──
        elif _SharedState.current_task == 3:
            score, feedback = grade_task3(action)
            _SharedState.scores.append(score)
            _SharedState.done = True

            final = round(sum(_SharedState.scores) / len(_SharedState.scores), 3)
            return EmailTriageObservation(
                task_id=3,
                task_description="Episode complete.",
                emails=[],
                reward=score,
                done=True,
                feedback=(
                    f"Task 3 result: {feedback} "
                    f"Episode finished! Final score: {final}/1.0 "
                    f"(Task scores: {_SharedState.scores})"
                ),
            )

        return EmailTriageObservation(
            task_id=_SharedState.current_task,
            task_description="Unexpected state.",
            emails=[],
            reward=0.0,
            done=True,
            feedback="Please call reset().",
        )

    def get_final_score(self) -> float:
        if not _SharedState.scores:
            return 0.0
        return round(sum(_SharedState.scores) / len(_SharedState.scores), 3)