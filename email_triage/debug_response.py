"""Quick debug — shows exact JSON structure from /reset and /step"""
import requests
import json

ENV_URL = "http://127.0.0.1:7860"

print("=== /reset response ===")
r = requests.post(f"{ENV_URL}/reset")
reset_data = r.json()
print(json.dumps(reset_data, indent=2))

print("\n=== /step response ===")
r2 = requests.post(
    f"{ENV_URL}/step",
    json={"action": {"task_id": 1, "label": "spam"}},
    headers={"Content-Type": "application/json"},
)
step_data = r2.json()
print(json.dumps(step_data, indent=2))

print("\n=== KEY STRUCTURE ===")
print("reset keys:", list(reset_data.keys()))
print("step keys:", list(step_data.keys()))
if "observation" in step_data:
    print("step observation keys:", list(step_data["observation"].keys()))
    print("reward value:", step_data["observation"].get("reward"))