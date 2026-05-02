import json
from pathlib import Path
from config import PATTERNS_FILE


class KnowledgeBase:
    def __init__(self):
        self.patterns = {}
        self.language_config = {}
        self._load()

    def _load(self):
        if PATTERNS_FILE.exists():
            data = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
            self.patterns = {p["id"]: p for p in data.get("patterns", [])}
            self.language_config = data.get("language_specific", {})

    def find_by_category(self, category: str) -> list[dict]:
        return [p for p in self.patterns.values() if p.get("category") == category]

    def match_patterns(self, code: str) -> list[dict]:
        import re
        matched = []
        for pat in self.patterns.values():
            if re.search(pat["pattern"], code, re.IGNORECASE):
                matched.append(pat)
        return matched

    def get_tools_for_language(self, language: str, tool_type: str) -> list[str]:
        lang = self.language_config.get(language, {})
        return lang.get(tool_type, [])

    def get_fix_template(self, pattern_id: str) -> str:
        pat = self.patterns.get(pattern_id, {})
        return pat.get("fix_template", "")
