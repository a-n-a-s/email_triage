"""Run inference against HF Space using local Ollama."""
import os
os.environ["ENV_BASE_URL"] = "https://akanaspro-email-triage.hf.space"
os.environ["API_BASE_URL"] = "http://localhost:11434/v1"
os.environ["MODEL_NAME"] = "llama3.2"
os.environ["HF_TOKEN"] = "ollama"

import sys
sys.argv = ["inference.py", "--episodes", "3"]
exec(compile(open("inference.py", encoding="utf-8").read(), "inference.py", "exec"))
