import re
from .base import BaseRule, Finding, Severity

COMPLEXITY_PATTERN = re.compile(r'^\s*(?:def |class |if |elif |else:|for |while |and |or |except)', re.I)

FUNCTION_LENGTH_LIMIT = 50
CLASS_LENGTH_LIMIT = 300
FILE_LENGTH_LIMIT = 1000
MAX_PARAMETERS = 7
MAX_NESTING = 4
MAX_RETURN_STATEMENTS = 4


class FunctionLengthRule(BaseRule):
    rule_id = "STD-001"
    category = "standards"
    severity = Severity.MEDIUM
    title = "Function Too Long"
    description = f"Function exceeds {FUNCTION_LENGTH_LIMIT} lines, consider extracting subroutines"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        lines = content.split("\n")
        current_func = None
        func_start = 0
        for i, line in enumerate(lines):
            if re.match(r'^\s*(?:def |async def )', line):
                if current_func and (i - func_start) > FUNCTION_LENGTH_LIMIT:
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=f"Function '{current_func}' is {i - func_start} lines (limit: {FUNCTION_LENGTH_LIMIT})",
                        file_path=file_path, line_start=func_start + 1, line_end=i,
                        code_snippet=lines[func_start].strip(),
                        suggestion="Extract logical blocks into smaller helper functions.",
                    ))
                current_func = line.strip().split("(")[0].replace("def ", "").replace("async def ", "")
                func_start = i
        if current_func and (len(lines) - func_start) > FUNCTION_LENGTH_LIMIT:
            findings.append(Finding(
                rule_id=self.rule_id, category=self.category,
                severity=self.severity, title=self.title,
                description=f"Function '{current_func}' is {len(lines) - func_start} lines",
                file_path=file_path, line_start=func_start + 1, line_end=len(lines),
                code_snippet=lines[func_start].strip(),
                suggestion="Extract logical blocks into smaller helper functions.",
            ))
        return findings


class TooManyParametersRule(BaseRule):
    rule_id = "STD-002"
    category = "standards"
    severity = Severity.LOW
    title = "Too Many Function Parameters"
    description = f"Function has more than {MAX_PARAMETERS} parameters"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            line_content = line.get("content", "")
            m = re.match(r'^\s*(?:async\s+)?def\s+\w+\s*\(([^)]*)\)', line_content)
            if m:
                params = [p.strip() for p in m.group(1).split(",") if p.strip() and p.strip() != "self" and not p.strip().startswith("*")]
                if len(params) > MAX_PARAMETERS:
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=f"Function has {len(params)} parameters (limit: {MAX_PARAMETERS})",
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line_content.strip(),
                        suggestion="Consider grouping parameters into a dataclass, Pydantic model, or dict.",
                    ))
        return findings


class DeepNestingRule(BaseRule):
    rule_id = "STD-003"
    category = "standards"
    severity = Severity.MEDIUM
    title = "Deeply Nested Code"
    description = f"Nesting depth exceeds {MAX_NESTING} levels, reducing readability"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            line_content = line.get("content", "")
            indent = len(line_content) - len(line_content.lstrip())
            depth = indent // 4
            if depth > MAX_NESTING:
                findings.append(Finding(
                    rule_id=self.rule_id, category=self.category,
                    severity=self.severity, title=self.title,
                    description=f"Nesting depth {depth} exceeds limit of {MAX_NESTING}",
                    file_path=file_path,
                    line_start=line.get("new_line", line.get("old_line", 0)),
                    code_snippet=line_content.strip(),
                    suggestion="Use early returns (guard clauses) or extract nested logic into separate functions.",
                ))
        return findings


class NamingConventionRule(BaseRule):
    rule_id = "STD-004"
    category = "standards"
    severity = Severity.LOW
    title = "Naming Convention Violation"
    description = "Variable or function name does not follow snake_case convention"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        bad_names = re.findall(
            r'(?:^|(?<=\s))([a-z]+(?:[A-Z][a-z0-9]+)+)\s*[:=]',
            "\n".join(l.get("content", "") for l in diff_lines)
        )
        for name in bad_names:
            if not name.startswith("__") and len(name) > 2:
                snake_name = re.sub(r'([A-Z])', r'_\1', name).lower()
                findings.append(Finding(
                    rule_id=self.rule_id, category=self.category,
                    severity=self.severity, title=self.title,
                    description=f"'{name}' uses camelCase, prefer snake_case",
                    file_path=file_path, line_start=0,
                    code_snippet=name,
                    suggestion=f"Rename '{name}' to '{snake_name}'.",
                ))
        return findings[:5]


class MissingDocstringRule(BaseRule):
    rule_id = "STD-005"
    category = "standards"
    severity = Severity.INFO
    title = "Missing Docstring on Public Function"
    description = "Public function lacks a docstring"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for i, line in enumerate(diff_lines):
            line_content = line.get("content", "")
            m = re.match(r'^\s*def\s+(\w+)', line_content)
            if m and not m.group(1).startswith("_"):
                if i + 1 < len(diff_lines):
                    next_content = diff_lines[i + 1].get("content", "")
                    if not re.match(r'^\s*"""', next_content) and not re.match(r"^\s*'''", next_content):
                        findings.append(Finding(
                            rule_id=self.rule_id, category=self.category,
                            severity=self.severity, title=self.title,
                            description=f"Public function '{m.group(1)}' missing docstring",
                            file_path=file_path,
                            line_start=line.get("new_line", line.get("old_line", 0)),
                            code_snippet=line_content.strip(),
                            suggestion="Add a docstring describing purpose, parameters, and return value.",
                            confidence=0.6,
                        ))
        return findings


class BareExceptRule(BaseRule):
    rule_id = "STD-006"
    category = "standards"
    severity = Severity.HIGH
    title = "Bare Except Clause"
    description = "Bare 'except:' catches all exceptions including KeyboardInterrupt"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            if re.match(r'^\s*except\s*:', line.get("content", "")):
                findings.append(Finding(
                    rule_id=self.rule_id, category=self.category,
                    severity=self.severity, title=self.title,
                    description="Bare except catches all exceptions indiscriminately",
                    file_path=file_path,
                    line_start=line.get("new_line", line.get("old_line", 0)),
                    code_snippet=line.get("content", "").strip(),
                    suggestion="Catch specific exceptions: 'except ValueError as e:'",
                ))
        return findings


class ExceptionPassRule(BaseRule):
    rule_id = "STD-007"
    category = "standards"
    severity = Severity.MEDIUM
    title = "Silenced Exception (except: pass)"
    description = "Exception caught but silently ignored"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        in_except = False
        for line in diff_lines:
            line_content = line.get("content", "")
            if re.match(r'^\s*except', line_content):
                in_except = True
                continue
            if in_except and re.match(r'^\s*pass\s*$', line_content):
                findings.append(Finding(
                    rule_id=self.rule_id, category=self.category,
                    severity=self.severity, title=self.title,
                    description="Exception caught but silently ignored with 'pass'",
                    file_path=file_path,
                    line_start=line.get("new_line", line.get("old_line", 0)),
                    code_snippet=line_content.strip(),
                    suggestion="At minimum, log the exception. If truly expected, add a comment explaining why.",
                ))
            in_except = False
        return findings


ALL_STANDARDS_RULES = [
    FunctionLengthRule(),
    TooManyParametersRule(),
    DeepNestingRule(),
    NamingConventionRule(),
    MissingDocstringRule(),
    BareExceptRule(),
    ExceptionPassRule(),
]
