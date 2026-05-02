import re
from .base import BaseRule, Finding, Severity

N_PLUS_1_PATTERNS = [
    re.compile(r'for\s+\w+\s+in\s+\w+:\s*\n*\s*\w+\.\w+\.filter\s*\(', re.I),
    re.compile(r'for\s+\w+\s+in\s+\w+:\s*\n*\s*\w+\.\w+\.get\s*\(', re.I),
    re.compile(r'\.forEach\s*\(.*(?:fetch|query|find|get)', re.I),
]

UNINDEXED_QUERY_PATTERNS = [
    re.compile(r'\.filter\s*\(\s*\w+__\w+', re.I),
    re.compile(r'WHERE\s+\w+\s*=', re.I),
]

INEFFICIENT_COLLECTION = [
    re.compile(r'\.append\s*\([^)]+\)\s*$.*\.sort\s*\(', re.MULTILINE | re.DOTALL),
    re.compile(r'for\s+\w+\s+in\s+\w+:\s*\n\s+if\s+\w+\s+in\s+\w+:\s*\n\s+\w+\.append', re.MULTILINE | re.DOTALL),
]

LARGE_LOOP_ALLOCATION = [
    re.compile(r'for\s+\w+\s+in\s+\w+:\s*\n\s*\w+\s*=\s*\[', re.MULTILINE | re.DOTALL),
]

MEMORY_LEAK_PATTERNS = [
    re.compile(r'@\w+\.register\s*\(', re.I),
    re.compile(r'addEventListener\s*\(.*(?!.*removeEventListener)', re.I),
    re.compile(r'global\s+\w+\s*= ', re.I),
]

BLOCKING_IO_PATTERNS = [
    re.compile(r'\.read\s*\(\s*\)\s*$', re.I),
    re.compile(r'time\.sleep\s*\(\s*\d+\s*\)', re.I),
    re.compile(r'\.wait\s*\(\s*\)', re.I),
]

UNBOUNDED_QUERY_PATTERNS = [
    re.compile(r'\.all\s*\(\s*\)(?!.*\[:|.*\.limit)', re.I),
    re.compile(r'Model\.objects\.all\s*\(\s*\)\s*$', re.I),
]


class NPlusOneRule(BaseRule):
    rule_id = "PERF-001"
    category = "performance"
    severity = Severity.HIGH
    title = "Potential N+1 Query"
    description = "Query executed inside a loop, causing N+1 database queries"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for i, line in enumerate(diff_lines):
            line_content = line.get("content", "")
            for pattern in N_PLUS_1_PATTERNS:
                if pattern.search(line_content):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line_content.strip(),
                        suggestion="Use select_related()/prefetch_related() in Django, "
                                    "eager loading in SQLAlchemy, or batch queries.",
                        references=["https://docs.djangoproject.com/en/stable/topics/db/optimization/"],
                    ))
        return findings


class UnindexedQueryRule(BaseRule):
    rule_id = "PERF-002"
    category = "performance"
    severity = Severity.MEDIUM
    title = "Potentially Unindexed Query"
    description = "Filter on a column that may not have an index"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            line_content = line.get("content", "")
            for pattern in UNINDEXED_QUERY_PATTERNS:
                if pattern.search(line_content):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line_content.strip(),
                        suggestion="Ensure the filtered column has a database index. Run EXPLAIN to verify.",
                        confidence=0.6,
                    ))
        return findings


class InefficientCollectionRule(BaseRule):
    rule_id = "PERF-003"
    category = "performance"
    severity = Severity.LOW
    title = "Inefficient Collection Usage"
    description = "Nested loops for lookup can be replaced with set/dict for O(1) lookup"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in INEFFICIENT_COLLECTION:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Use set or dict for O(1) membership tests instead of list.",
                    ))
        return findings


class UnboundedQueryRule(BaseRule):
    rule_id = "PERF-004"
    category = "performance"
    severity = Severity.HIGH
    title = "Unbounded Query Without Limit"
    description = ".all() without .limit() or pagination may return too many rows"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in UNBOUNDED_QUERY_PATTERNS:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Add .limit(N) or use pagination to control result size.",
                    ))
        return findings


class BlockingIORule(BaseRule):
    rule_id = "PERF-005"
    category = "performance"
    severity = Severity.MEDIUM
    title = "Blocking I/O in Async Context"
    description = "Synchronous blocking call in an async-capable context may degrade performance"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in BLOCKING_IO_PATTERNS:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Use async/await alternatives or run blocking I/O in a thread pool executor.",
                    ))
        return findings


ALL_PERFORMANCE_RULES = [
    NPlusOneRule(),
    UnindexedQueryRule(),
    InefficientCollectionRule(),
    UnboundedQueryRule(),
    BlockingIORule(),
]
