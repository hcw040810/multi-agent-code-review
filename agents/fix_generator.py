"""Agent 3: Fix Generator — 自动生成修复建议和 patch 文件"""

import json
from dataclasses import dataclass, field
from typing import Optional

from rules import Finding
from rules.base import Severity
from knowledge_base import KnowledgeBase
from utils.llm import chat


FIX_SYSTEM_PROMPT = """You are an expert code fixer. Given a code finding, generate a precise fix.

Return ONLY valid JSON with this structure:
{
  "fix_description": "description of the proposed fix",
  "fix_type": "replace|insert|delete|restructure",
  "original_code": "the problematic code",
  "fixed_code": "the corrected code",
  "side_effects": ["list of potential side effects"],
  "confidence": 0.0-1.0,
  "requires_testing": true/false,
  "rollback_plan": "how to revert if fix causes issues"
}
"""

PATCH_SYSTEM_PROMPT = """You are an expert at generating git patches. Generate a unified diff format patch.

The patch MUST apply cleanly. Include the correct --- and +++ headers and @@ hunk headers.

Return ONLY valid JSON:
{
  "patch": "the unified diff patch text",
  "description": "what this patch changes",
  "files_modified": ["list of files"]
}
"""


@dataclass
class FixSuggestion:
    finding: Finding
    fix_description: str = ""
    fix_type: str = ""
    original_code: str = ""
    fixed_code: str = ""
    patch: str = ""
    side_effects: list[str] = field(default_factory=list)
    confidence: float = 0.0
    requires_testing: bool = True
    rollback_plan: str = ""

    def to_dict(self) -> dict:
        return {
            "finding": self.finding.to_dict(),
            "fix_description": self.fix_description,
            "fix_type": self.fix_type,
            "original_code": self.original_code,
            "fixed_code": self.fixed_code,
            "patch": self.patch,
            "side_effects": self.side_effects,
            "confidence": self.confidence,
            "requires_testing": self.requires_testing,
            "rollback_plan": self.rollback_plan,
        }


class FixGeneratorAgent:
    """基于发现的问题自动生成修复方案和 patch"""

    def __init__(self):
        self.kb = KnowledgeBase()
        self.suggestions: list[FixSuggestion] = []
        self.chain_context: list[dict] = []
        self.repaired_count = 0

    def generate(self, findings: list[Finding], auto_apply: bool = False,
                 repo_path: str = "") -> list[FixSuggestion]:
        self.suggestions = []
        self.chain_context = []
        self.repaired_count = 0

        critical_high = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        medium = [f for f in findings if f.severity == Severity.MEDIUM]
        low_info = [f for f in findings if f.severity in (Severity.LOW, Severity.INFO)]

        prioritized = critical_high + medium + low_info

        self.chain_context.append({
            "agent": "FixGenerator",
            "stage": "prioritization",
            "reasoning": f"按优先级排序: {len(critical_high)} critical/high, {len(medium)} medium, {len(low_info)} low/info. 先处理高风险项。",
        })

        for finding in prioritized:
            suggestion = self._generate_fix(finding)
            if suggestion:
                self.suggestions.append(suggestion)

                if suggestion.confidence > 0.7 and suggestion.patch and auto_apply:
                    self._apply_patch(suggestion, repo_path)

        repaired = sum(1 for s in self.suggestions if s.patch)
        self.repaired_count = repaired
        self.chain_context.append({
            "agent": "FixGenerator",
            "stage": "generation_done",
            "reasoning": f"为 {len(self.suggestions)} 个问题生成了修复方案，其中 {repaired} 个可自动修复",
        })

        return self.suggestions

    def _generate_fix(self, finding: Finding) -> Optional[FixSuggestion]:
        kb_fix = self.kb.get_fix_template(finding.rule_id)
        if kb_fix:
            suggestion = FixSuggestion(
                finding=finding,
                fix_description=kb_fix,
                fix_type="replace",
                confidence=0.8,
            )
            suggestion.patch = self._generate_patch_from_suggestion(finding, suggestion)
            return suggestion

        for pat in self.kb.match_patterns(finding.code_snippet):
            suggestion = FixSuggestion(
                finding=finding,
                fix_description=pat["fix_template"],
                fix_type="replace",
                confidence=0.7,
            )
            suggestion.patch = self._generate_patch_from_suggestion(finding, suggestion)
            return suggestion

        return self._llm_generate_fix(finding)

    def _llm_generate_fix(self, finding: Finding) -> Optional[FixSuggestion]:
        user_content = f"""
Finding Details:
- Rule: {finding.rule_id}
- Severity: {finding.severity.value}
- Category: {finding.category}
- Title: {finding.title}
- Description: {finding.description}
- File: {finding.file_path}
- Code: {finding.code_snippet}

Generate a precise fix for this issue."""
        try:
            response = chat([
                {"role": "system", "content": FIX_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ], json_mode=True)

            data = json.loads(response)
            suggestion = FixSuggestion(
                finding=finding,
                fix_description=data.get("fix_description", ""),
                fix_type=data.get("fix_type", "replace"),
                original_code=data.get("original_code", finding.code_snippet),
                fixed_code=data.get("fixed_code", ""),
                side_effects=data.get("side_effects", []),
                confidence=data.get("confidence", 0.5),
                requires_testing=data.get("requires_testing", True),
                rollback_plan=data.get("rollback_plan", ""),
            )

            if suggestion.fixed_code and suggestion.original_code:
                suggestion.patch = self._generate_patch_from_suggestion(finding, suggestion)

            return suggestion
        except Exception:
            return FixSuggestion(
                finding=finding,
                fix_description=finding.suggestion or "Manual review required",
                fix_type="review",
                confidence=0.1,
            )

    def _generate_patch_from_suggestion(self, finding: Finding, suggestion: FixSuggestion) -> str:
        if not suggestion.original_code or not suggestion.fixed_code:
            return ""

        file_path = finding.file_path.replace("\\", "/")
        patch = f"""--- a/{file_path}
+++ b/{file_path}
@@ -{finding.line_start},1 +{finding.line_start},1 @@
-{suggestion.original_code.strip()}
+{suggestion.fixed_code.strip()}
"""
        return patch

    def _apply_patch(self, suggestion: FixSuggestion, repo_path: str) -> bool:
        if not suggestion.patch or not repo_path:
            return False
        from utils.git_ops import apply_patch
        return apply_patch(repo_path, suggestion.patch)

    def get_chain_context(self) -> list[dict]:
        return self.chain_context
