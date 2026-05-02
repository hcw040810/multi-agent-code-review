"""Multi-Agent 协作管道 — 链式推理闭环: 问题定位→原因分析→修复建议→测试验证"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from agents.pr_parser import PRParserAgent, PRContext
from agents.rule_checker import RuleCheckerAgent
from agents.fix_generator import FixGeneratorAgent, FixSuggestion
from agents.test_runner import TestRunnerAgent, TestRunReport
from rules import Finding
from utils.report import (
    print_banner, print_agent_step, print_findings,
    print_finding_detail, print_summary, save_report,
    print_chain_reasoning,
)
from rich.console import Console

console = Console()


@dataclass
class PipelineResult:
    success: bool = True
    pr_context: Optional[PRContext] = None
    findings: list[Finding] = field(default_factory=list)
    suggestions: list[FixSuggestion] = field(default_factory=list)
    test_report: Optional[TestRunReport] = None
    score: int = 100
    chain_reasoning: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str = ""


class CodeReviewPipeline:
    """4-Agent 协作闭环: Parse → Check → Fix → Test"""

    def __init__(self, repo_path: str, base_branch: str = "main",
                 use_llm: bool = True, auto_fix: bool = False,
                 verbose: bool = True, interactive: bool = False):
        self.repo_path = repo_path
        self.base_branch = base_branch
        self.use_llm = use_llm
        self.auto_fix = auto_fix
        self.verbose = verbose
        self.interactive = interactive

        self.parser = PRParserAgent(repo_path, base_branch)
        self.checker = RuleCheckerAgent()
        self.fixer = FixGeneratorAgent()
        self.tester = TestRunnerAgent(repo_path)

    def run(self) -> PipelineResult:
        start = time.time()
        result = PipelineResult()
        chain: list[dict] = []

        try:
            if self.verbose:
                print_banner()

            # =============================================
            # Phase 1: PR Parser — 结构分析
            # =============================================
            if self.verbose:
                print_agent_step("Agent1: PR Parser", "start", "解析 PR 结构和变更内容")
            pr_ctx = self.parser.analyze(use_unstaged=(self.base_branch == "HEAD"))
            result.pr_context = pr_ctx
            chain.extend(self.parser.get_chain_context())

            if self.verbose:
                print_agent_step("Agent1: PR Parser", "done",
                    f"{len(pr_ctx.files)} 文件, {pr_ctx.total_changes} 行变更, 风险: {pr_ctx.risk_assessment}")
                console.print(f"  [dim]语言: {', '.join(pr_ctx.languages)} | {pr_ctx.summary}[/dim]")

            if not pr_ctx.files:
                result.error = "No changed files detected"
                result.success = False
                result.duration_seconds = time.time() - start
                return result

            # =============================================
            # Phase 2: Rule Checker — 规则检测
            # =============================================
            if self.verbose:
                print_agent_step("Agent2: Rule Checker", "start", "安全/性能/规范 多维检测")

            findings = self.checker.check(pr_ctx, use_llm=self.use_llm)
            result.findings = findings
            chain.extend(self.checker.get_chain_context())

            if self.verbose:
                print_agent_step("Agent2: Rule Checker", "done",
                    f"发现 {len(findings)} 个问题, 质量评分: {self.checker.calculate_score()}/100")

            # 链式推理输出
            chain.append({
                "agent": "ChainReasoning",
                "stage": "problem_analysis",
                "reasoning": self._build_chain_reasoning(findings),
            })

            # 交互模式：展示详细发现
            if self.interactive and findings:
                self._interactive_review(findings)

            # =============================================
            # Phase 3: Fix Generator — 自动修复
            # =============================================
            if findings:
                if self.verbose:
                    print_agent_step("Agent3: Fix Generator", "start", "为检测到的问题生成修复方案")

                suggestions = self.fixer.generate(findings, auto_apply=self.auto_fix, repo_path=self.repo_path)
                result.suggestions = suggestions
                chain.extend(self.fixer.get_chain_context())

                if self.verbose:
                    print_agent_step("Agent3: Fix Generator", "done",
                        f"生成 {len(suggestions)} 个修复方案, {self.fixer.repaired_count} 个可自动修复")

                chain.append({
                    "agent": "ChainReasoning",
                    "stage": "fix_analysis",
                    "reasoning": self._build_fix_chain(suggestions),
                })

                # 交互模式：逐个确认修复
                if self.interactive and suggestions:
                    self._interactive_fixes(suggestions)
            else:
                if self.verbose:
                    print_agent_step("Agent3: Fix Generator", "skip", "无问题需修复")

            # =============================================
            # Phase 4: Test Runner — 回归验证
            # =============================================
            if self.verbose:
                print_agent_step("Agent4: Test Runner", "start", "运行测试并验证修复")

            original_report = TestRunReport()
            generated_tests = self.tester.generate_tests_for_findings(findings) if findings else None
            test_report = self.tester.run(pr_ctx, generated_tests=generated_tests)
            result.test_report = test_report
            chain.extend(self.tester.get_chain_context())

            if self.verbose:
                print_agent_step("Agent4: Test Runner", "done",
                    f"{test_report.passed}/{test_report.total} 通过 ({test_report.success_rate:.0f}%)"
                    + (f" [red]回归检测![/red]" if test_report.regression_detected else ""))

            # =============================================
            # Phase 5: 验证修复
            # =============================================
            if result.suggestions and self.fixer.repaired_count > 0:
                if self.verbose:
                    print_agent_step("Verification", "start", "验证修复后的回归检测")
                result.test_report = self.tester.verify_fixes(result.suggestions, test_report)
                chain.extend(self.tester.get_chain_context())
                if self.verbose:
                    print_agent_step("Verification", "done")

            # =============================================
            # Summary
            # =============================================
            result.score = self.checker.calculate_score()
            result.duration_seconds = time.time() - start
            result.chain_reasoning = chain

            if self.verbose:
                console.print()
                print_summary(
                    findings,
                    result.score,
                    repaired_count=self.fixer.repaired_count,
                )

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.duration_seconds = time.time() - start
            if self.verbose:
                console.print(f"[red]Pipeline error: {e}[/red]")

        return result

    def _build_chain_reasoning(self, findings: list[Finding]) -> str:
        if not findings:
            return "代码审查未发现明显问题，代码质量良好。"

        parts = []
        by_cat = {}
        for f in findings:
            by_cat.setdefault(f.category, []).append(f)

        for cat, items in by_cat.items():
            top = sorted(items, key=lambda x: x.severity.value)[:3]
            parts.append(f"{cat}: {', '.join(t.title for t in top)}")

        return f"问题定位: 发现 {len(findings)} 个问题涉及 {len(by_cat)} 个类别。{'; '.join(parts)}"

    def _build_fix_chain(self, suggestions: list[FixSuggestion]) -> str:
        high_conf = [s for s in suggestions if s.confidence > 0.7]
        low_conf = [s for s in suggestions if s.confidence <= 0.7]

        parts = []
        if high_conf:
            parts.append(f"{len(high_conf)} 个高置信度修复可自动应用")
        if low_conf:
            parts.append(f"{len(low_conf)} 个需人工审查")

        return f"修复分析: {'; '.join(parts)}" if parts else "无可用修复方案"

    def _interactive_review(self, findings: list[Finding]) -> None:
        console.print("\n[bold yellow]Interactive Review Mode[/bold yellow]")
        for i, f in enumerate(findings):
            print_finding_detail(f)
            if i >= 10:
                console.print(f"[dim]... and {len(findings) - 10} more findings[/dim]")
                break

    def _interactive_fixes(self, suggestions: list[FixSuggestion]) -> None:
        console.print("\n[bold yellow]Fix Review[/bold yellow]")
        for s in suggestions:
            if s.confidence > 0.7:
                console.print(f"  [green]✓[/green] {s.finding.title} — {s.fix_description}")
            else:
                console.print(f"  [yellow]?[/yellow] {s.finding.title} — {s.fix_description} (需人工审查)")

    def save_report(self, output_dir: str = ".") -> Path:
        output_path = Path(output_dir) / f"code-review-report-{int(time.time())}.json"
        metadata = {
            "repo_path": self.repo_path,
            "base_branch": self.base_branch,
            "score": self.checker.calculate_score(),
            "repaired_count": self.fixer.repaired_count,
        }
        return save_report(self.checker.all_findings, output_path, metadata)
