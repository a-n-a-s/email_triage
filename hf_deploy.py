"""
Deploy Email Triage to Hugging Face Spaces.

Usage:
    # Set your HF token
    $env:HF_TOKEN = "hf_your_token"

    # Run deploy
    python hf_deploy.py
"""

import os
from huggingface_hub import HfApi

# Configuration
REPO_ID = "akanaspro/email-triage"
FOLDER_PATH = "D:/email_triage/email_triage"

# Files/folders to exclude
IGNORE_PATTERNS = [
    "venv/**",
    "__pycache__/**",
    "*.pyc",
    "*.db",
    "*.egg-info/**",
    ".github/**",
    ".qwen/**",
    "*.log",
    "inference_log.txt",
    "inference_results.json",
    "demo_inference_results.json",
    "requirements.lock",
    "submission and rules.txt",
    ".env",
]

def main():
    api = HfApi()

    # Verify token
    token = os.getenv("HF_TOKEN")
    if not token:
        print("❌  HF_TOKEN not set")
        print("    $env:HF_TOKEN = 'hf_your_token'")
        return

    print(f"🚀  Deploying to {REPO_ID}")
    print(f"📁  Source: {FOLDER_PATH}")
    print(f"🚫  Excluding: {len(IGNORE_PATTERNS)} patterns")
    print("")

    try:
        commit_info = api.upload_folder(
            folder_path=FOLDER_PATH,
            repo_id=REPO_ID,
            repo_type="space",
            ignore_patterns=IGNORE_PATTERNS,
            commit_message="Deploy Email Triage environment",
        )
        print("✅  Deploy successful!")
        print(f"🔗  Space URL: https://huggingface.co/spaces/{REPO_ID}")
        print(f"📝  Commit: {commit_info}")
    except Exception as e:
        print(f"❌  Deploy failed: {e}")
        print("")
        print("    If you see a 504 timeout, the files may have uploaded anyway.")
        print("    Check: https://huggingface.co/spaces/akanaspro/email-triage")

if __name__ == "__main__":
    main()
