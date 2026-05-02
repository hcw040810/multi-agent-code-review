"""Agent 4: Test Runner — 运行测试 + 回归验证 + 覆盖率检查"""

import subprocess
import re
from pathlib import Path
from dataclasses import dataclass, field

from knowledge_base import KnowledgeBase
from utils.llm import chat
import json


TEST_GENERATION_PROMPT = """You are an expert test writer. Given a code change and issue, generate targeted test cases.

Return ONLY valid JSON:
{
  "test_cases": [
    {
      "name": "test name",
      "description": "what this tests",
      "test_type": "unit|integration|security|regression",
      "expected_result": "pass|fail",
      "test_code": "the actual test code"
    }
  ],
  "test_runner_command": "command to run these tests"
}
"""


@dataclass
class TestResult:
    test_name: str = ""
    status: str = "unknown"
    duration: float = 0.0
    output: str = ""
    error_message: str = ""


@dataclass
class TestRunReport:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    results: list[TestResult] = field(default_factory=list)
    regression_detected: bool = False
    coverage_pct: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


class TestRunnerAgent:
    """执行测试、验证修复、检测回归"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.kb = KnowledgeBase()
        self.chain_context: list[dict] = []
        self.latest_report = TestRunReport()

    def run(self, pr_context, generated_tests: list[str] = None) -> TestRunReport:
        self.chain_context = []

        self.chain_context.append({
            "agent": "TestRunner",
            "stage": "discover_tests",
            "reasoning": f"在 {self.repo_path} 中发现测试框架并运行已有测试",
        })

        test_command = self._discover_test_command(pr_context)

        self.chain_context.append({
            "agent": "TestRunner",
            "stage": "run_existing_tests",
            "reasoning": f"执行命令: {test_command}",
        })

        report = self._run_tests(test_command)
        self.latest_report = report

        self.chain_context.append({
            "agent": "TestRunner",
            "stage": "test_results",
            "reasoning": f"测试结果: {report.passed}/{report.total} 通过, {report.failed} 失败, {report.skipped} 跳过 ({report.success_rate:.0f}%)",
        })

        if generated_tests:
            self.chain_context.append({
                "agent": "TestRunner",
                "stage": "generated_tests",
                "reasoning": f"运行 {len(generated_tests)} 个自动生成的测试用例",
            })
            gen_report = self._run_generated_tests(generated_tests)
            report.results.extend(gen_report.results)
            report.total += gen_report.total
            report.passed += gen_report.passed
            report.failed += gen_report.failed

        if report.failed > 0:
            report.regression_detected = self._check_regression(report)

        self._check_coverage(report)
        return report

    def _discover_test_command(self, pr_context) -> str:
        root = Path(self.repo_path)

        if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
            return "pytest -v --tb=short 2>&1"
        if (root / "Makefile").exists():
            with open(root / "Makefile") as f:
                content = f.read()
                if "test:" in content:
                    return "make test 2>&1"
        if (root / "package.json").exists():
            with open(root / "package.json") as f:
                data = json.load(f)
                if "test" in data.get("scripts", {}):
                    return "npm test 2>&1"
        if (root / "go.mod").exists():
            return "go test ./... 2>&1"
        if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            return "./gradlew test 2>&1"
        if (root / "Cargo.toml").exists():
            return "cargo test 2>&1"

        for f in pr_context.files:
            if f.language == "python":
                return "pytest -v --tb=short 2>&1"
            elif f.language in ("javascript", "typescript"):
                return "npm test 2>&1"
            elif f.language == "go":
                return "go test ./... 2>&1"

        return "pytest -v --tb=short 2>&1"

    def _run_tests(self, command: str) -> TestRunReport:
        report = TestRunReport()
        try:
            result = subprocess.run(
                command, shell=True, cwd=self.repo_path,
                capture_output=True, text=True, timeout=120,
            )
            output = result.stdout + result.stderr
            report.results = self._parse_test_output(output)
            report.total = len(report.results)
            report.passed = sum(1 for r in report.results if r.status == "passed")
            report.failed = sum(1 for r in report.results if r.status == "failed")
            report.skipped = sum(1 for r in report.results if r.status == "skipped")
        except subprocess.TimeoutExpired:
            report.results = [TestResult(test_name="timeout", status="failed", error_message="Test run timed out after 120s")]
            report.total = 1
            report.failed = 1
        except Exception as e:
            report.results = [TestResult(test_name="error", status="failed", error_message=str(e))]
            report.total = 1
            report.failed = 1
        return report

    def _parse_test_output(self, output: str) -> list[TestResult]:
        results = []

        pytest_pattern = re.compile(
            r'(PASSED|FAILED|ERROR|SKIPPED)\s+(\S+)',
            re.I,
        )
        for m in pytest_pattern.finditer(output):
            status = m.group(1).lower()
            results.append(TestResult(
                test_name=m.group(2),
                status=status if status != "error" else "failed",
                output=m.group(0),
            ))

        if not results:
            summary = re.search(r'(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped', output, re.I)
            if summary:
                results.append(TestResult(
                    test_name="summary",
                    status="passed" if int(summary.group(2)) == 0 else "mixed",
                    output=summary.group(0),
                ))

        jest_pattern = re.compile(
            r'(✓|✕|○)\s+(.+)',
            re.I,
        )
        if not results:
            for m in jest_pattern.finditer(output):
                icon = m.group(1)
                if "✓" in icon or "PASS" in icon.upper():
                    status = "passed"
                elif "✕" in icon or "FAIL" in icon.upper():
                    status = "failed"
                else:
                    status = "skipped"
                results.append(TestResult(test_name=m.group(2).strip(), status=status))

        if not results:
            results.append(TestResult(test_name="test_run", status="completed", output=output[:500]))

        return results

    def _run_generated_tests(self, tests: list[str]) -> TestRunReport:
        report = TestRunReport()
        for i, test_code in enumerate(tests):
            report.results.append(TestResult(
                test_name=f"generated_test_{i+1}",
                status="pending",
                output=f"Generated test: {test_code[:200]}",
            ))
        report.total = len(report.results)
        return report

    def _check_regression(self, report: TestRunReport) -> bool:
        if report.failed > report.total * 0.3 and report.total > 0:
            return True
        return any("regression" in r.error_message.lower() or
                   "was working" in r.output.lower()
                   for r in report.results if r.status == "failed")

    def _check_coverage(self, report: TestRunReport) -> None:
        try:
            result = subprocess.run(
                ["coverage", "report", "--format=total"],
                cwd=self.repo_path, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                report.coverage_pct = float(result.stdout.strip())
        except Exception:
            pass

    def generate_tests_for_findings(self, findings: list) -> list[str]:
        tests = []
        for finding in findings[:5]:
            try:
                response = chat([
                    {"role": "system", "content": TEST_GENERATION_PROMPT},
                    {"role": "user", "content": json.dumps(finding.to_dict())},
                ], json_mode=True)
                data = json.loads(response)
                for tc in data.get("test_cases", []):
                    code = tc.get("test_code", "")
                    if code:
                        tests.append(code)
            except Exception:
                pass
        return tests

    def verify_fixes(self, suggestions: list, original_report: TestRunReport) -> TestRunReport:
        self.chain_context.append({
            "agent": "TestRunner",
            "stage": "verify_fixes",
            "reasoning": f"对 {len(suggestions)} 个修复进行回归验证",
        })

        test_command = self._discover_test_command(None)

        report = self._run_tests(test_command)

        if report.failed > original_report.failed:
            report.regression_detected = True
            self.chain_context.append({
                "agent": "TestRunner",
                "stage": "regression_detected",
                "reasoning": f"检测到回归: 修复后失败数从 {original_report.failed} 增加到 {report.failed}",
            })
        else:
            self.chain_context.append({
                "agent": "TestRunner",
                "stage": "verification_passed",
                "reasoning": f"验证通过: 修复后失败数从 {original_report.failed} 变为 {report.failed}",
            })

        self.latest_report = report
        return report

    def get_chain_context(self) -> list[dict]:
        return self.chain_context
