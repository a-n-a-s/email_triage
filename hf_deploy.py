"""Deploy Email Triage to Hugging Face Spaces."""
import os
from huggingface_hub import HfApi

api = HfApi()
REPO_ID = "akanaspro/email-triage"
FOLDER_PATH = "D:/email_triage/email_triage"

# Ignore local files
IGNORE_PATTERNS = [
    "venv/**", "__pycache__/**", "*.pyc", "*.db", "*.egg-info/**", 
    ".github/**", ".qwen/**", "*.log", "inference_log.txt", 
    "inference_results.json", "requirements.lock", ".env"
]

print(f"🚀  Deploying to {REPO_ID}...")

api.upload_folder(
    folder_path=FOLDER_PATH,
    repo_id=REPO_ID,
    repo_type="space",
    ignore_patterns=IGNORE_PATTERNS,
    commit_message="Fix: Expose /reset and /step at root for validation"
)
print("✅  Deployed! Check Space status.")
