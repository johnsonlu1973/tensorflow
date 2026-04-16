import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "sessions"

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
PERPLEXITY_API_KEY: str = os.environ.get("PERPLEXITY_API_KEY", "")

INTEL_MODEL = "claude-opus-4-7"
SYNTHESIS_MAX_TOKENS = 8192

SESSIONS_DIR.mkdir(exist_ok=True)
