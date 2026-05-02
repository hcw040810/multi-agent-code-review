#!/usr/bin/env python3
"""Multi-Agent Code Review System — 多 Agent 协作代码审查 + 自动修复闭环

Agent1: PR Parser     — 结构分析 + diff 理解
Agent2: Rule Checker   — 安全/性能/规范检测
Agent3: Fix Generator  — 自动修复方案生成
Agent4: Test Runner    — 测试执行 + 回归验证

Usage:
    # Review current uncommitted changes
    python main.py --repo /path/to/repo

    # Review PR against main branch
    python main.py --repo /path/to/repo --base main

    # Full pipeline with LLM deep scan and auto-fix
    python main.py --repo /path/to/repo --base main --llm --auto-fix

    # Interactive mode: review each finding
    python main.py --repo /path/to/repo --interactive

    # Save report to file
    python main.py --repo /path/to/repo --output reports/
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.traceback import install as install_rich_tb

from pipeline import CodeReviewPipeline

install_rich_tb()
console = Console()


@click.command()
@click.option("--repo", "-r", default=".", help="Path to the git repository")
@click.option("--base", "-b", default="main", help="Base branch for diff comparison")
@click.option("--llm/--no-llm", default=True, help="Enable LLM deep scan (default: on)")
@click.option("--auto-fix/--no-auto-fix", default=False, help="Auto-apply high-confidence fixes (default: off)")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode: review each finding")
@click.option("--output", "-o", default=None, help="Save report to directory")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output (summary only)")
@click.option("--detail/--summary-only", default=False, help="Show detailed findings (default: summary only)")
def main(repo: str, base: str, llm: bool, auto_fix: bool,
         interactive: bool, output: str, quiet: bool, detail: bool):
    """Multi-Agent Code Review System — 4-Agent 协作闭环"""

    repo_path = Path(repo).resolve()
    if not (repo_path / ".git").exists():
        console.print(f"[red]Error: {repo_path} is not a git repository[/red]")
        sys.exit(1)

    if not quiet:
        console.print(f"[dim]Repository: {repo_path}[/dim]")
        console.print(f"[dim]Base branch: {base}[/dim]")

    pipeline = CodeReviewPipeline(
        repo_path=str(repo_path),
        base_branch=base,
        use_llm=llm,
        auto_fix=auto_fix,
        verbose=not quiet,
        interactive=interactive,
    )

    result = pipeline.run()

    # Detail mode: show individual findings
    if detail and result.findings:
        console.print()
        for f in result.findings:
            from utils.report import print_finding_detail
            print_finding_detail(f)

    # Chain reasoning output
    if detail and result.chain_reasoning:
        console.print()
        from utils.report import print_chain_reasoning
        print_chain_reasoning(result.chain_reasoning)

    # Save report
    if output:
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = pipeline.save_report(str(output_dir))
        console.print(f"\n[green]Report saved: {report_path}[/green]")

    # Exit code based on findings
    critical_count = sum(1 for f in result.findings if f.severity.value == "critical")
    if critical_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
