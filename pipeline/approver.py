"""
Interactive approval loop.
Renders each Pass 2 issue in a Rich panel and prompts the user to
approve (y), skip (n), or quit reviewing (q).
Approved fixes are applied in-place to the optimised resume.
"""

import copy
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich import box

from pipeline.utils import apply_fix_to_resume, ISSUE_TYPE_LABELS

console = Console()

SEVERITY_STYLE = {
    "high":   "bold red",
    "medium": "bold yellow",
    "low":    "dim white",
}


def _render_issue(issue: dict, index: int, total: int) -> None:
    severity   = issue.get("severity", "low")
    issue_type = ISSUE_TYPE_LABELS.get(issue.get("issue_type", ""), issue.get("issue_type", ""))
    style      = SEVERITY_STYLE.get(severity, "white")

    table = Table(
        box=box.ROUNDED,
        show_header=False,
        border_style="bright_black",
        pad_edge=True,
        expand=True,
    )
    table.add_column("Field",   style="dim",   width=18, no_wrap=True)
    table.add_column("Content", style="white", ratio=1)

    table.add_row("Section",       f"[cyan]{issue.get('section', '—')}[/cyan]")
    table.add_row("Issue",         f"[{style}]{issue_type}[/{style}]")
    table.add_row("Severity",      f"[{style}]{severity.upper()}[/{style}]")
    table.add_row("─" * 16,        "─" * 50)
    table.add_row("Current",       f"[red]{issue.get('original', '—')}[/red]")
    table.add_row("Suggested fix", f"[green]{issue.get('suggested_fix', '—')}[/green]")
    table.add_row("Why",           f"[dim]{issue.get('explanation', '—')}[/dim]")

    console.print(
        Panel(
            table,
            title=f"[bold]Issue {index} of {total}[/bold]",
            border_style=style,
            padding=(0, 1),
        )
    )


def run_approval_loop(optimized: dict, issues: list[dict]) -> dict:
    """
    Walks through all issues, renders each one, and prompts for approval.
    Returns the (possibly mutated) final resume dict.
    """
    if not issues:
        console.print("\n[bold green]✓ No issues found. Resume is ready.[/bold green]\n")
        return optimized

    final    = copy.deepcopy(optimized)
    total    = len(issues)
    approved = skipped = 0

    console.print(
        f"\n[bold yellow]⚙  Pass 2 identified [white]{total}[/white] issue(s) to review.[/bold yellow]\n"
    )

    for i, issue in enumerate(issues, start=1):
        _render_issue(issue, i, total)

        choice = Prompt.ask(
            "  [bold]Apply fix?[/bold] [[green]y[/green]/[red]n[/red]/[dim]q to stop[/dim]]",
            choices=["y", "n", "q"],
            default="y",
            show_choices=False,
        )

        if choice == "q":
            remaining = total - i
            console.print(
                f"\n[dim]Stopped early. {remaining} remaining issue(s) skipped.[/dim]"
            )
            break

        if choice == "y":
            apply_fix_to_resume(final, issue)
            approved += 1
            console.print("  [green]✓ Fix applied.[/green]\n")
        else:
            skipped += 1
            console.print("  [dim]Skipped.[/dim]\n")

    console.rule("[bold]Review Complete[/bold]")
    summary = Text()
    summary.append(f"  {approved} fix(es) applied", style="bold green")
    summary.append("  ·  ", style="dim")
    summary.append(f"{skipped} skipped", style="dim yellow")
    console.print(summary)
    console.print()

    return final
