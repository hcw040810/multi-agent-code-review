from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    rule_id: str
    category: str
    severity: Severity
    title: str
    description: str
    file_path: str
    line_start: int
    line_end: int = 0
    code_snippet: str = ""
    suggestion: str = ""
    confidence: float = 1.0
    cwe_id: str = ""
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end or self.line_start,
            "code_snippet": self.code_snippet,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "cwe_id": self.cwe_id,
            "references": self.references,
        }


class BaseRule(ABC):
    rule_id: str = ""
    category: str = ""
    severity: Severity = Severity.MEDIUM
    title: str = ""
    description: str = ""

    @abstractmethod
    def check(self, file_path: str, content: str, diff_lines: list[dict]) -> list[Finding]:
        ...
