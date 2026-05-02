import re
from .base import BaseRule, Finding, Severity


SQL_INJECTION_PATTERNS = [
    re.compile(r'execute\s*\(\s*(?:f["\']|["\'].*%[sdr]).*\b(request\.|params\[|body\[)', re.I),
    re.compile(r'\.execute\s*\(\s*["\'].*\{\w+}.*["\'].*\.format\s*\(', re.I),
    re.compile(r'cursor\.execute\s*\(\s*[\w\d_]+', re.I),
]

XSS_PATTERNS = [
    re.compile(r'innerHTML\s*=', re.I),
    re.compile(r'\.html\s*\(\s*(?!.*escape|.*sanitize)', re.I),
    re.compile(r'dangerouslySetInnerHTML', re.I),
    re.compile(r'v-html\s*=', re.I),
    re.compile(r'bypassSecurityTrust\w+', re.I),
]

COMMAND_INJECTION_PATTERNS = [
    re.compile(r'os\.system\s*\(', re.I),
    re.compile(r'subprocess\.(call|Popen|run)\s*\(.*shell\s*=\s*True', re.I),
    re.compile(r'exec\s*\(\s*(?!.*compile)', re.I),
    re.compile(r'eval\s*\(', re.I),
]

HARDCODED_SECRET_PATTERNS = [
    (re.compile(r'(?:password|passwd|secret|api_key|apikey|token|auth)\s*[:=]\s*["\'][^"\']{8,}["\']', re.I), Severity.CRITICAL),
    (re.compile(r'(?:private_key|ssh_key|access_key)\s*[:=]\s*["\'][^"\']{16,}["\']', re.I), Severity.CRITICAL),
    (re.compile(r'-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----', re.I), Severity.CRITICAL),
]

INSECURE_DESERIALIZATION = [
    re.compile(r'pickle\.(loads?|dump)', re.I),
    re.compile(r'yaml\.load\s*\(\s*(?!.*SafeLoader)', re.I),
    re.compile(r'marshal\.loads?', re.I),
]

PATH_TRAVERSAL_PATTERNS = [
    re.compile(r'os\.path\.join\s*\(.*(?:request\.|user_input|params\[)', re.I),
    re.compile(r'open\s*\(.*(?:request\.|user_input|params\[)', re.I),
]

WEAK_CRYPTO = [
    re.compile(r'hashlib\.(md5|sha1)\s*\(', re.I),
    re.compile(r'random\.(random|choice|randint)\s*\(', re.I),
    re.compile(r'DES\.new|cryptography.*\.MODE_ECB', re.I),
]


class SQLInjectionRule(BaseRule):
    rule_id = "SEC-001"
    category = "security"
    severity = Severity.CRITICAL
    title = "Potential SQL Injection"
    description = "String formatting or concatenation in SQL query may allow SQL injection attacks"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in SQL_INJECTION_PATTERNS:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Use parameterized queries or ORM methods. "
                                    "e.g., cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
                        cwe_id="CWE-89",
                        references=["https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"],
                    ))
        return findings


class XSSRule(BaseRule):
    rule_id = "SEC-002"
    category = "security"
    severity = Severity.HIGH
    title = "Potential Cross-Site Scripting (XSS)"
    description = "Unescaped user content in HTML context may allow XSS attacks"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in XSS_PATTERNS:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Use proper HTML escaping or sanitization. "
                                    "For React: avoid dangerouslySetInnerHTML. For Vue: avoid v-html.",
                        cwe_id="CWE-79",
                        references=["https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html"],
                    ))
        return findings


class CommandInjectionRule(BaseRule):
    rule_id = "SEC-003"
    category = "security"
    severity = Severity.CRITICAL
    title = "Potential Command Injection"
    description = "User input used in shell commands may allow command injection"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in COMMAND_INJECTION_PATTERNS:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Use subprocess.run() with shell=False and a list of arguments. "
                                    "Avoid os.system(), exec(), and eval() with user input.",
                        cwe_id="CWE-78",
                        references=["https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html"],
                    ))
        return findings


class HardcodedSecretRule(BaseRule):
    rule_id = "SEC-004"
    category = "security"
    severity = Severity.CRITICAL
    title = "Hardcoded Secret Detected"
    description = "Hardcoded credentials or API keys in source code"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            line_content = line.get("content", "")
            for pattern, severity in HARDCODED_SECRET_PATTERNS:
                m = pattern.search(line_content)
                if m:
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line_content.strip(),
                        suggestion="Move secrets to environment variables or a secure vault. "
                                    "Use os.environ.get('SECRET_KEY') or a secrets manager.",
                        cwe_id="CWE-798",
                        references=["https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html"],
                    ))
        return findings


class InsecureDeserializationRule(BaseRule):
    rule_id = "SEC-005"
    category = "security"
    severity = Severity.HIGH
    title = "Insecure Deserialization"
    description = "Using unsafe deserialization that may lead to RCE"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in INSECURE_DESERIALIZATION:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Use safe serialization: json instead of pickle, "
                                    "yaml.SafeLoader instead of yaml.load().",
                        cwe_id="CWE-502",
                    ))
        return findings


class WeakCryptoRule(BaseRule):
    rule_id = "SEC-006"
    category = "security"
    severity = Severity.MEDIUM
    title = "Weak Cryptographic Algorithm"
    description = "Using weak or deprecated cryptographic algorithms"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in WEAK_CRYPTO:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Use strong cryptographic algorithms: "
                                    "hashlib.sha256(), secrets module for randomness.",
                        cwe_id="CWE-327",
                    ))
        return findings


class PathTraversalRule(BaseRule):
    rule_id = "SEC-007"
    category = "security"
    severity = Severity.HIGH
    title = "Potential Path Traversal"
    description = "User input used in file path construction may allow path traversal"

    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        findings = []
        for line in diff_lines:
            for pattern in PATH_TRAVERSAL_PATTERNS:
                if pattern.search(line.get("content", "")):
                    findings.append(Finding(
                        rule_id=self.rule_id, category=self.category,
                        severity=self.severity, title=self.title,
                        description=self.description,
                        file_path=file_path,
                        line_start=line.get("new_line", line.get("old_line", 0)),
                        code_snippet=line.get("content", "").strip(),
                        suggestion="Validate and sanitize user input. Use os.path.basename() "
                                    "or a whitelist of allowed paths.",
                        cwe_id="CWE-22",
                    ))
        return findings


ALL_SECURITY_RULES = [
    SQLInjectionRule(),
    XSSRule(),
    CommandInjectionRule(),
    HardcodedSecretRule(),
    InsecureDeserializationRule(),
    WeakCryptoRule(),
    PathTraversalRule(),
]
