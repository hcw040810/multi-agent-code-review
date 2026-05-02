import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

RULES_DIR = PROJECT_ROOT / "rules"
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
PATTERNS_FILE = KNOWLEDGE_BASE_DIR / "patterns.json"

DEFAULT_IGNORE_PATTERNS = [
    "*.lock", "*.json", "*.md", "*.txt", "*.png", "*.jpg", "*.gif",
    "*.svg", "*.ico", "*.woff*", "*.ttf", "*.eot", "*.map",
    "__pycache__/*", "*.pyc", "*.pyo", ".git/*", "node_modules/*",
    "vendor/*", "dist/*", "build/*", ".env", ".env.*",
]

SEVERITY_LEVELS = ["critical", "high", "medium", "low", "info"]

RULE_CATEGORIES = {
    "security": {"weight": 10, "description": "Security vulnerabilities"},
    "performance": {"weight": 7, "description": "Performance issues"},
    "standards": {"weight": 5, "description": "Code standards violations"},
    "logic": {"weight": 8, "description": "Logic errors"},
    "maintainability": {"weight": 4, "description": "Maintainability concerns"},
}
