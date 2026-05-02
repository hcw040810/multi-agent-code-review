"""Agent 1: PR Parser — 结构分析 + diff 理解 + 变更分类"""

import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from utils.llm import chat
from utils.git_ops import (
    get_changed_files, get_file_diff, get_unified_diff,
    get_unstaged_diff, get_staged_diff, parse_diff_to_lines,
    get_current_branch, get_file_content,
)


@dataclass
class ChangedFile:
    path: str
    language: str
    change_type: str
    lines_added: int = 0
    lines_removed: int = 0
    content: str = ""
    diff_lines: list[dict] = field(default_factory=list)

    @property
    def extension(self) -> str:
        return Path(self.path).suffix.lower()


@dataclass
class PRContext:
    repo_path: str
    base_branch: str
    current_branch: str
    title: str = ""
    description: str = ""
    files: list[ChangedFile] = field(default_factory=list)
    summary: str = ""
    risk_assessment: str = ""

    @property
    def total_changes(self) -> int:
        return sum(f.lines_added + f.lines_removed for f in self.files)

    @property
    def languages(self) -> list[str]:
        return list(set(f.language for f in self.files if f.language != "unknown"))


LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".jsx": "javascript", ".go": "go",
    ".rs": "rust", ".java": "java", ".kt": "kotlin",
    ".swift": "swift", ".c": "c", ".cpp": "cpp", ".h": "c",
    ".rb": "ruby", ".php": "php", ".cs": "csharp",
    ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
    ".tf": "terraform", ".sh": "shell", ".dockerfile": "dockerfile",
    ".html": "html", ".css": "css", ".scss": "scss",
    ".vue": "vue", ".svelte": "svelte",
}

CHANGE_TYPE_PATTERNS = [
    (re.compile(r'(?:security|auth|login|password|token|secret|csrf|xss|sqli)', re.I), "security"),
    (re.compile(r'(?:performance|perf|optimize|cache|index|fast|slow)', re.I), "performance"),
    (re.compile(r'(?:test|spec|mock|fixture)', re.I), "testing"),
    (re.compile(r'(?:config|setting|env|docker|k8s|deploy)', re.I), "configuration"),
    (re.compile(r'(?:api|endpoint|route|controller|view)', re.I), "api"),
    (re.compile(r'(?:model|schema|migration|entity|orm)', re.I), "data_model"),
    (re.compile(r'(?:component|ui|css|style|template|render)', re.I), "frontend"),
    (re.compile(r'(?:refactor|cleanup|rename|move)', re.I), "refactoring"),
    (re.compile(r'(?:bug|fix|hotfix|patch|issue)', re.I), "bugfix"),
    (re.compile(r'(?:docs|readme|changelog|doc)', re.I), "documentation"),
    (re.compile(r'(?:dependency|dep|upgrade|bump|package)', re.I), "dependencies"),
]


class PRParserAgent:
    """解析 PR 的结构、变更内容和风险等级"""

    def __init__(self, repo_path: str, base_branch: str = "main"):
        self.repo_path = repo_path
        self.base_branch = base_branch
        self.chain_context: list[dict] = []

    def analyze(self, use_unstaged: bool = False) -> PRContext:
        self.chain_context.append({
            "agent": "PRParser",
            "stage": "structure_analysis",
            "reasoning": "开始解析 PR 结构，识别变更文件和变更类型",
        })

        current_branch = get_current_branch(self.repo_path)
        ctx = PRContext(
            repo_path=self.repo_path,
            base_branch=self.base_branch,
            current_branch=current_branch,
        )

        if use_unstaged:
            changed_files = self._get_unstaged_files()
            diff_text = get_unstaged_diff(self.repo_path)
        else:
            try:
                changed_files = get_changed_files(self.repo_path, self.base_branch)
                diff_text = get_unified_diff(self.repo_path, self.base_branch)
            except Exception:
                changed_files = self._get_unstaged_files()
                diff_text = get_unstaged_diff(self.repo_path)

        self.chain_context.append({
            "agent": "PRParser",
            "stage": "file_discovery",
            "reasoning": f"发现 {len(changed_files)} 个变更文件, diff 总量 {len(diff_text)} 字符",
        })

        for file_path in changed_files:
            cf = self._analyze_file(file_path)
            ctx.files.append(cf)

        ctx.summary = self._generate_summary(ctx)
        ctx.risk_assessment = self._assess_risk(ctx)

        self.chain_context.append({
            "agent": "PRParser",
            "stage": "risk_assessment",
            "reasoning": f"风险评估: {ctx.risk_assessment}",
        })

        return ctx

    def _get_unstaged_files(self) -> list[str]:
        import subprocess
        result = subprocess.run(
            ["git", "-C", self.repo_path, "diff", "--name-only"],
            capture_output=True, text=True,
        )
        staged = subprocess.run(
            ["git", "-C", self.repo_path, "diff", "--cached", "--name-only"],
            capture_output=True, text=True,
        )
        files = set()
        for out in [result.stdout, staged.stdout]:
            for f in out.split("\n"):
                if f.strip():
                    files.add(f.strip())
        return list(files)

    def _analyze_file(self, file_path: str) -> ChangedFile:
        ext = Path(file_path).suffix.lower()
        language = LANGUAGE_MAP.get(ext, "unknown")

        try:
            diff = get_file_diff(self.repo_path, file_path, self.base_branch)
        except Exception:
            diff = ""

        diff_lines = parse_diff_to_lines(diff)
        lines_added = sum(1 for l in diff_lines if l.get("type") == "added")
        lines_removed = sum(1 for l in diff_lines if l.get("type") == "removed")

        change_type = self._classify_change(file_path, diff_lines)
        content = get_file_content(self.repo_path, file_path) or ""

        return ChangedFile(
            path=file_path,
            language=language,
            change_type=change_type,
            lines_added=lines_added,
            lines_removed=lines_removed,
            content=content,
            diff_lines=diff_lines,
        )

    def _classify_change(self, file_path: str, diff_lines: list[dict]) -> str:
        added_text = " ".join(l.get("content", "") for l in diff_lines if l.get("type") == "added")
        context = f"{file_path} {added_text}"

        for pattern, change_type in CHANGE_TYPE_PATTERNS:
            if pattern.search(context):
                return change_type
        return "general"

    def _generate_summary(self, ctx: PRContext) -> str:
        if not ctx.files:
            return "No changes detected."

        parts = []
        types = {}
        for f in ctx.files:
            types[f.change_type] = types.get(f.change_type, 0) + 1

        parts.append(f"Branch: {ctx.current_branch} → {ctx.base_branch}")
        parts.append(f"Files: {len(ctx.files)} changed ({ctx.total_changes} lines)")
        parts.append(f"Languages: {', '.join(ctx.languages)}")
        parts.append(f"Change types: {', '.join(f'{v}x {k}' for k, v in sorted(types.items(), key=lambda x: -x[1]))}")
        return " | ".join(parts)

    def _assess_risk(self, ctx: PRContext) -> str:
        risk_score = 0
        reasons = []

        if ctx.total_changes > 500:
            risk_score += 3
            reasons.append("large diff (>500 lines)")

        has_security = any(f.change_type == "security" for f in ctx.files)
        if has_security:
            risk_score += 2
            reasons.append("security-related changes")

        has_data = any(f.change_type == "data_model" for f in ctx.files)
        if has_data:
            risk_score += 2
            reasons.append("data model changes")

        has_config = any(f.change_type == "configuration" for f in ctx.files)
        if has_config:
            risk_score += 1
            reasons.append("configuration changes")

        if risk_score >= 5:
            return f"HIGH risk — {', '.join(reasons)}"
        elif risk_score >= 3:
            return f"MEDIUM risk — {', '.join(reasons)}"
        elif risk_score >= 1:
            return f"LOW risk — {', '.join(reasons)}"
        return "MINIMAL risk"

    def get_chain_context(self) -> list[dict]:
        return self.chain_context
