from .base import BaseRule, Finding, Severity
from .security import ALL_SECURITY_RULES
from .performance import ALL_PERFORMANCE_RULES
from .standards import ALL_STANDARDS_RULES

ALL_RULES = ALL_SECURITY_RULES + ALL_PERFORMANCE_RULES + ALL_STANDARDS_RULES

__all__ = ["BaseRule", "Finding", "Severity", "ALL_RULES",
           "ALL_SECURITY_RULES", "ALL_PERFORMANCE_RULES", "ALL_STANDARDS_RULES"]
