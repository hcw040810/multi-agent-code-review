"""Agent 2: Rule Checker — 安全/性能/规范三重检测 + LLM 深度分析"""

import json
from typing import Optional

from rules import ALL_RULES, Finding
from rules.base import Severity
from knowledge_base import KnowledgeBase
from utils.llm import chat, review_with_context

SECURITY_SYSTEM_PROMPT = """You are an expert security code reviewer. Analyze the provided code diff for security vulnerabilities:

1. Authentication & Authorization bypass
2. Injection flaws (SQL, NoSQL, Command, LDAP, etc.)
3. Sensitive data exposure
4. Broken access control
5. Security misconfiguration
6. Using vulnerable/outdated components
7. Insufficient logging & monitoring
8. SSRF, XXE, and deserialization flaws

For each finding, return ONLY valid JSON:
{"findings": [{"title": "...", "severity": "critical|high|medium|low|info", "description": "...", "line_hint": "code snippet or line reference", "suggestion": "specific fix", "cwe_id": "CWE-XXX or empty"}]}
"""

PERFORMANCE_SYSTEM_PROMPT = """You are an expert performance reviewer. Analyze code for:

1. N+1 query patterns
2. Missing indexes / inefficient queries
3. Unnecessary allocations or copies
4. Blocking I/O in async context
5. Unbounded collections or queries
6. Memory leaks
7. Inefficient algorithms

Return ONLY valid JSON:
{"findings": [{"title": "...", "severity": "critical|high|medium|low|info", "description": "...", "line_hint": "...", "suggestion": "specific optimization"}]}
"""

STANDARDS_SYSTEM_PROMPT = """You are an expert code standards reviewer. Analyze code for:

1. Naming convention violations
2. Missing error handling
3. Overly complex functions
4. Dead code / unreachable code
5. Inconsistent patterns
6. Missing type hints/annotations
7. Comment quality issues
8. Code duplication

Return ONLY valid JSON:
{"findings": [{"title": "...", "severity": "critical|high|medium|low|info", "description": "...", "line_hint": "...", "suggestion": "..."}]}
"""


class RuleCheckerAgent:
    """基于规则引擎 + LLM 的多维代码检测"""

    def __init__(self):
        self.kb = KnowledgeBase()
        self.all_findings: list[Finding] = []
        self.chain_context: list[dict] = []
        self._rules = ALL_RULES

    def check(self, pr_context, use_llm: bool = True) -> list[Finding]:
        self.all_findings = []
        self.chain_context = []

        self.chain_context.append({
            "agent": "RuleChecker",
            "stage": "rule_scan_start",
            "reasoning": f"对 {len(pr_context.files)} 个文件执行 {len(self._rules)} 条规则的静态扫描",
        })

        for changed_file in pr_context.files:
            file_findings = self._scan_file(changed_file)
            self.all_findings.extend(file_findings)

        rule_count = len(self.all_findings)
        self.chain_context.append({
            "agent": "RuleChecker",
            "stage": "rule_scan_done",
            "reasoning": f"静态规则扫描发现 {rule_count} 条问题",
        })

        if use_llm and pr_context.files:
            llm_findings = self._llm_deep_scan(pr_context)
            self.all_findings.extend(llm_findings)
            self.chain_context.append({
                "agent": "RuleChecker",
                "stage": "llm_deep_scan_done",
                "reasoning": f"LLM 深度扫描额外发现 {len(llm_findings)} 条问题",
            })

        self.all_findings.sort(key=lambda f: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}[f.severity.value]
        ))

        return self.all_findings

    def _scan_file(self, changed_file) -> list[Finding]:
        findings = []
        for rule in self._rules:
            try:
                result = rule.check(
                    changed_file.path,
                    changed_file.content,
                    changed_file.diff_lines,
                )
                findings.extend(result)
            except Exception:
                pass
        return findings

    def _llm_deep_scan(self, pr_context) -> list[Finding]:
        findings: list[Finding] = []

        for changed_file in pr_context.files:
            if not changed_file.content.strip():
                continue

            diff_text = "\n".join(
                l.get("content", "")
                for l in changed_file.diff_lines
                if l.get("type") == "added"
            )

            if changed_file.language in ("python", "javascript", "typescript", "go", "java", "ruby", "php"):
                for prompt, category in [
                    (SECURITY_SYSTEM_PROMPT, "security"),
                    (PERFORMANCE_SYSTEM_PROMPT, "performance"),
                    (STANDARDS_SYSTEM_PROMPT, "standards"),
                ]:
                    try:
                        findings.extend(
                            self._call_llm_check(changed_file, diff_text, prompt, category)
                        )
                    except Exception:
                        pass

        return findings

    def _call_llm_check(self, changed_file, diff_text: str, system_prompt: str, category: str) -> list[Finding]:
        findings: list[Finding] = []
        response = review_with_context(system_prompt, changed_file.content, diff_text)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return findings

        for item in data.get("findings", []):
            severity_str = item.get("severity", "medium").lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.MEDIUM

            findings.append(Finding(
                rule_id=f"LLM-{category[:4].upper()}-{len(findings):03d}",
                category=category,
                severity=severity,
                title=item.get("title", "LLM detected issue"),
                description=item.get("description", ""),
                file_path=changed_file.path,
                line_start=0,
                code_snippet=item.get("line_hint", ""),
                suggestion=item.get("suggestion", ""),
                cwe_id=item.get("cwe_id", ""),
                confidence=0.7,
            ))
        return findings

    def calculate_score(self) -> int:
        if not self.all_findings:
            return 100

        weights = {
            "critical": 25, "high": 15, "medium": 8,
            "low": 3, "info": 1,
        }
        penalty = sum(
            weights.get(f.severity.value, 0) * f.confidence
            for f in self.all_findings
        )
        return max(0, 100 - penalty)

    def get_chain_context(self) -> list[dict]:
        return self.chain_context
