import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich import box

console = Console()

SEVERITY_COLORS = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "blue",
    "info": "dim",
}

SEVERITY_ICONS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}


def print_banner():
    console.print(Panel.fit(
        "[bold cyan]Multi-Agent Code Review System[/bold cyan]\n"
        "[dim]PR Parser → Rule Checker → Fix Generator → Test Runner[/dim]",
        border_style="cyan",
        padding=(1, 2),
    ))


def print_findings(findings: list) -> None:
    if not findings:
        console.print("[green]No issues found.[/green]")
        return

    table = Table(title="Review Findings", box=box.ROUNDED, header_style="bold white")
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Category", width=12)
    table.add_column("Rule", width=12)
    table.add_column("Title", width=30)
    table.add_column("File", width=25)
    table.add_column("Line", width=6, justify="right")

    for f in findings:
        color = SEVERITY_COLORS.get(f.severity.value, "white")
        table.add_row(
            f"[{color}]{f.severity.value.upper()}[/{color}]",
            f.category,
            f.rule_id,
            f.title,
            str(Path(f.file_path).name) if f.file_path else "-",
            str(f.line_start),
        )
    console.print(table)


def print_finding_detail(finding) -> None:
    color = SEVERITY_COLORS.get(finding.severity.value, "white")
    icon = SEVERITY_ICONS.get(finding.severity.value, "")

    lines = [
        f"{icon} [{color}]{finding.severity.value.upper()}[/{color}] - {finding.title}",
        f"[dim]Rule: {finding.rule_id} | Category: {finding.category} | File: {finding.file_path}:{finding.line_start}[/dim]",
        f"",
        f"[bold]Description:[/bold] {finding.description}",
    ]
    if finding.code_snippet:
        lines.append(f"[bold]Code:[/bold]")
        lines.append(f"  [dim]{finding.code_snippet}[/dim]")
    if finding.suggestion:
        lines.append(f"[bold]Suggestion:[/bold] {finding.suggestion}")
    if finding.cwe_id:
        lines.append(f"[bold]CWE:[/bold] {finding.cwe_id}")
    if finding.references:
        lines.append(f"[bold]References:[/bold]")
        for ref in finding.references:
            lines.append(f"  - {ref}")

    console.print(Panel("\n".join(lines), border_style=color, padding=(1, 2)))


def print_summary(findings: list, score: int, repaired_count: int = 0) -> None:
    counts = {}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1

    summary = Table(title="Review Summary", box=box.ROUNDED)
    summary.add_column("Metric", style="bold")
    summary.add_column("Value")

    summary.add_row("Total Findings", str(len(findings)))
    summary.add_row("Critical", str(counts.get("critical", 0)))
    summary.add_row("High", str(counts.get("high", 0)))
    summary.add_row("Medium", str(counts.get("medium", 0)))
    summary.add_row("Low", str(counts.get("low", 0)))
    summary.add_row("Info", str(counts.get("info", 0)))

    if score >= 90:
        grade = "[green]A[/green]"
    elif score >= 75:
        grade = "[blue]B[/blue]"
    elif score >= 60:
        grade = "[yellow]C[/yellow]"
    elif score >= 40:
        grade = "[orange1]D[/orange1]"
    else:
        grade = "[red]F[/red]"

    summary.add_row("Quality Score", f"{score}/100 {grade}")
    if repaired_count:
        summary.add_row("Auto-Repaired", str(repaired_count))

    console.print(summary)


def print_agent_step(agent_name: str, status: str, detail: str = "") -> None:
    icon_map = {
        "start": "▶",
        "done": "✓",
        "fail": "✗",
        "skip": "○",
    }
    icon = icon_map.get(status, "•")
    color_map = {
        "start": "cyan",
        "done": "green",
        "fail": "red",
        "skip": "dim",
    }
    c = color_map.get(status, "white")
    console.print(f"  [{c}]{icon} {agent_name}[/{c}]" + (f" [dim]- {detail}[/dim]" if detail else ""))


def save_report(findings: list, output_path: Path, metadata: dict = None) -> Path:
    report = {
        "generated_at": datetime.now().isoformat(),
        "metadata": metadata or {},
        "total_findings": len(findings),
        "findings": [f.to_dict() for f in findings],
    }
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return output_path


def print_chain_reasoning(chain: list[dict]) -> None:
    for step in chain:
        console.print(Panel(
            f"[bold]{step.get('stage', 'Unknown')}[/bold]\n\n{step.get('reasoning', '')}",
            title=f"Chain: {step.get('agent', '')}",
            border_style="magenta",
            padding=(1, 2),
        ))
