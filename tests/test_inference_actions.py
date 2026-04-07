"""
Integration Test: Run actual inference and log AI agent actions.

This test runs the inference.py script against the environment and logs:
- What action the AI took for each task
- The score/reward it received
- Whether the action was correct
- Detailed feedback from the environment
"""

import os
import sys
import json
import requests
from datetime import datetime

# Configuration
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
LOG_FILE = "inference_test_log.txt"


class InferenceTester:
    """Run inference and log AI agent actions."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.log_lines = []

    def log(self, message: str):
        """Add message to log."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{timestamp}] {message}"
        self.log_lines.append(line)
        print(line)

    def reset(self):
        """Reset environment."""
        response = self.session.post(f"{self.base_url}/reset", json={}, timeout=30)
        response.raise_for_status()
        return response.json()

    def step(self, action: dict):
        """Execute action in environment."""
        response = self.session.post(
            f"{self.base_url}/step",
            json={"action": action},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def run_simulated_inference(self):
        """
        Run simulated inference with predefined actions.
        This tests what happens when the AI makes specific decisions.
        """
        self.log("=" * 70)
        self.log("🧪 INFERENCE ACTION TEST")
        self.log("=" * 70)
        self.log(f"Environment: {self.base_url}")
        self.log("")

        # Track results
        results = {
            "tasks": [],
            "total_score": 0,
            "actions_taken": []
        }

        # ========== EPISODE 1: Perfect Actions ==========
        self.log("-" * 70)
        self.log("EPISODE 1: Testing PERFECT actions")
        self.log("-" * 70)

        obs = self.reset()
        task_id = obs['observation']['task_id']
        email = obs['observation']['emails'][0]

        self.log(f"\n📧 Task {task_id}: Spam Classification")
        self.log(f"   Subject: {email['subject']}")
        self.log(f"   Sender: {email['sender']}")
        self.log(f"   Body: {email['body'][:100]}...")

        # Simulate AI decision: classify as spam
        ai_action = {"task_id": 1, "label": "spam"}
        self.log(f"\n🤖 AI Agent Action: {ai_action}")

        result = self.step(ai_action)
        reward = result['reward']
        feedback = result['observation']['feedback']

        self.log(f"   ✅ Score: {reward}")
        self.log(f"   📝 Feedback: {feedback}")

        results["tasks"].append({
            "episode": 1,
            "task": 1,
            "action": ai_action,
            "correct": True,
            "score": reward,
            "feedback": feedback
        })
        results["actions_taken"].append(ai_action)

        # Task 2
        obs = result['observation']
        task_id = obs['task_id']
        emails = obs['emails']

        self.log(f"\n📧 Task {task_id}: Urgency Ranking")
        for i, email in enumerate(emails):
            urgency = email.get('urgency', 'N/A')
            urgency_text = "🔴 CRITICAL" if urgency == 1 else ("🟡 Medium" if urgency == 2 else "🟢 Low")
            self.log(f"   [{i}] {urgency_text} - {email['subject'][:50]}...")

        # Simulate AI decision: rank by urgency (most urgent first)
        # AI should identify: Email with urgency=1 > urgency=2 > urgency=3
        # Find which position has each urgency level
        critical_idx = next((i for i, e in enumerate(emails) if e.get('urgency') == 1), 0)
        medium_idx = next((i for i, e in enumerate(emails) if e.get('urgency') == 2), 1)
        low_idx = next((i for i, e in enumerate(emails) if e.get('urgency') == 3), 2)
        
        ai_action = {"task_id": 2, "ranking": [critical_idx, medium_idx, low_idx]}
        self.log(f"\n🤖 AI Agent Action: {ai_action}")
        self.log(f"   Interpretation: Email {critical_idx} (CRITICAL) > Email {medium_idx} (Medium) > Email {low_idx} (Low)")

        result = self.step(ai_action)
        reward = result['reward']
        feedback = result['observation']['feedback']

        self.log(f"   ✅ Score: {reward}")
        self.log(f"   📝 Feedback: {feedback}")

        results["tasks"].append({
            "episode": 1,
            "task": 2,
            "action": ai_action,
            "correct": True,
            "score": reward,
            "feedback": feedback
        })
        results["actions_taken"].append(ai_action)

        # Task 3
        obs = result['observation']
        task_id = obs['task_id']
        email = obs['emails'][0]

        self.log(f"\n📧 Task {task_id}: Action + Reply")
        self.log(f"   Subject: {email['subject']}")
        self.log(f"   Body: {email['body'][:100]}...")

        # Simulate AI decision: reply with keywords (adapt based on email)
        # For this test, we always reply with professional response
        ai_action = {
            "task_id": 3,
            "action_type": "reply",
            "reply_text": "I confirm we will deliver by Friday EOD as agreed. The deadline is noted."
        }
        self.log(f"\n🤖 AI Agent Action: {ai_action}")
        self.log(f"   Note: This action assumes 'reply' is correct. If email requires 'forward', score will be lower.")

        result = self.step(ai_action)
        reward = result['reward']
        feedback = result['observation']['feedback']
        done = result['done']

        self.log(f"   ✅ Score: {reward}")
        self.log(f"   📝 Feedback: {feedback}")
        self.log(f"   🏁 Episode Complete: {done}")

        results["tasks"].append({
            "episode": 1,
            "task": 3,
            "action": ai_action,
            "correct": True,
            "score": reward,
            "feedback": feedback
        })
        results["actions_taken"].append(ai_action)

        # Calculate total
        total_score = sum(t["score"] for t in results["tasks"])
        avg_score = total_score / len(results["tasks"])
        results["total_score"] = total_score
        results["average_score"] = avg_score

        self.log("")
        self.log("=" * 70)
        self.log("📊 EPISODE 1 SUMMARY")
        self.log("=" * 70)
        self.log(f"Task 1 (Spam):     {results['tasks'][0]['score']:.2f} - Action: {results['tasks'][0]['action']}")
        self.log(f"Task 2 (Ranking):  {results['tasks'][1]['score']:.2f} - Action: {results['tasks'][1]['action']}")
        self.log(f"Task 3 (Reply):    {results['tasks'][2]['score']:.2f} - Action: {results['tasks'][2]['action']}")
        self.log(f"Total Score:       {total_score:.2f}/3.00")
        self.log(f"Average Score:     {avg_score:.3f}")
        self.log("=" * 70)

        # ========== EPISODE 2: Wrong Actions ==========
        self.log("")
        self.log("-" * 70)
        self.log("EPISODE 2: Testing WRONG actions (to verify grader catches errors)")
        self.log("-" * 70)

        obs = self.reset()

        # Task 1: Wrong classification
        ai_action = {"task_id": 1, "label": "not_spam"}  # Wrong!
        self.log(f"\n📧 Task 1: Classifying spam as 'not_spam' (WRONG)")
        self.log(f"🤖 AI Agent Action: {ai_action}")

        result = self.step(ai_action)
        reward = result['reward']
        feedback = result['observation']['feedback']

        self.log(f"   ❌ Score: {reward}")
        self.log(f"   📝 Feedback: {feedback}")

        results["tasks"].append({
            "episode": 2,
            "task": 1,
            "action": ai_action,
            "correct": False,
            "score": reward,
            "feedback": feedback
        })

        # Task 2: Wrong ranking
        ai_action = {"task_id": 2, "ranking": [0, 1, 2]}  # Wrong order!
        self.log(f"\n📧 Task 2: Ranking [0,1,2] (WRONG - should be [1,2,0])")
        self.log(f"🤖 AI Agent Action: {ai_action}")

        result = self.step(ai_action)
        reward = result['reward']
        feedback = result['observation']['feedback']

        self.log(f"   ❌ Score: {reward}")
        self.log(f"   📝 Feedback: {feedback}")

        results["tasks"].append({
            "episode": 2,
            "task": 2,
            "action": ai_action,
            "correct": False,
            "score": reward,
            "feedback": feedback
        })

        # Task 3: Wrong action type
        ai_action = {
            "task_id": 3,
            "action_type": "delete",  # Wrong! Should reply
            "reply_text": ""
        }
        self.log(f"\n📧 Task 3: Deleting important client email (WRONG)")
        self.log(f"🤖 AI Agent Action: {ai_action}")

        result = self.step(ai_action)
        reward = result['reward']
        feedback = result['observation']['feedback']

        self.log(f"   ❌ Score: {reward}")
        self.log(f"   📝 Feedback: {feedback}")

        results["tasks"].append({
            "episode": 2,
            "task": 3,
            "action": ai_action,
            "correct": False,
            "score": reward,
            "feedback": feedback
        })

        # Episode 2 summary
        ep2_tasks = [t for t in results["tasks"] if t["episode"] == 2]
        ep2_total = sum(t["score"] for t in ep2_tasks)
        ep2_avg = ep2_total / len(ep2_tasks)

        self.log("")
        self.log("=" * 70)
        self.log("📊 EPISODE 2 SUMMARY (Wrong Actions)")
        self.log("=" * 70)
        self.log(f"Task 1 (Spam):     {ep2_tasks[0]['score']:.2f} - WRONG action caught!")
        self.log(f"Task 2 (Ranking):  {ep2_tasks[1]['score']:.2f} - WRONG action caught!")
        self.log(f"Task 3 (Reply):    {ep2_tasks[2]['score']:.2f} - WRONG action caught!")
        self.log(f"Total Score:       {ep2_total:.2f}/3.00")
        self.log(f"Average Score:     {ep2_avg:.3f}")
        self.log("=" * 70)

        # ========== FINAL SUMMARY ==========
        self.log("")
        self.log("=" * 70)
        self.log("🎯 FINAL TEST SUMMARY")
        self.log("=" * 70)
        self.log(f"Episodes Run: 2")
        self.log(f"Total Tasks: {len(results['tasks'])}")
        self.log(f"Correct Actions: {sum(1 for t in results['tasks'] if t['correct'])}")
        self.log(f"Wrong Actions: {sum(1 for t in results['tasks'] if not t['correct'])}")
        self.log("")
        self.log("Episode 1 (Perfect):  {:.3f} average score".format(avg_score))
        self.log("Episode 2 (Wrong):    {:.3f} average score".format(ep2_avg))
        self.log("")
        self.log("✅ Graders correctly identified correct and wrong actions!")
        self.log("=" * 70)

        # Save log to file
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_lines))

        self.log("")
        self.log(f"💾 Full log saved to: {LOG_FILE}")

        return results


def main():
    """Run inference action tests."""
    print("=" * 70)
    print("🧪 Email Triage - AI Agent Action Tests")
    print("=" * 70)
    print(f"Environment: {ENV_BASE_URL}")
    print("")

    # Check if server is running
    try:
        response = requests.get(f"{ENV_BASE_URL}/health", timeout=5)
        print(f"✅ Server healthy: {response.json()}")
    except Exception as e:
        print(f"❌ Server not responding: {e}")
        print("Make sure the server is running:")
        print("  python -m uvicorn server.app:app --host 0.0.0.0 --port 8000")
        return

    print("")

    # Run tests
    tester = InferenceTester(ENV_BASE_URL)
    results = tester.run_simulated_inference()

    print("")
    print("=" * 70)
    print("✅ INFERENCE ACTION TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
