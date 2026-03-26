"""
tailor — AI-powered ATS resume optimiser

DEFAULT behaviour (no flags) → generic optimisation:
    tailor

JD-based optimisation — --jd flag triggers the full JD pipeline:
    tailor --jd google_swe.txt --company-name Google
    tailor --jd google_swe.txt --company-name Google --template-id abc123 --resume-name "Google SWE 2025"

--template-id and --resume-name are optional for both modes;
if omitted the CLI will prompt interactively before publishing.
--company-name is REQUIRED when --jd is provided.
"""

import typer
from rich.console import Console
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.prompt import Prompt

app     = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
console = Console()

def _print_header(mode_label: str) -> None:
    title    = Text("tailor", style="bold cyan")
    subtitle = Text(f"Mode: {mode_label}", style="dim white")
    console.print(Panel(f"{title}\n{subtitle}", border_style="cyan", padding=(0, 2)))
    console.print()


def _print_ats_scores(baseline: dict, post_p1: dict) -> None:
    from pipeline.scorer import score_delta
    delta  = score_delta(baseline, post_p1)
    sign   = "+" if delta["composite_delta"] >= 0 else ""
    colour = "green" if delta["composite_delta"] >= 0 else "red"

    console.print(Rule("[bold]ATS Score Report[/bold]"))
    console.print(
        f"  Baseline     [dim]→[/dim] [yellow]{baseline['composite_ats_score']}[/yellow]  "
        f"(keywords {baseline['keyword_hit_rate']}%  ·  semantic {baseline['semantic_similarity']}%)"
    )
    console.print(
        f"  After Pass 1 [dim]→[/dim] [{colour}]{post_p1['composite_ats_score']}[/{colour}]  "
        f"([{colour}]{sign}{delta['composite_delta']}[/{colour}])  "
        f"(keywords {post_p1['keyword_hit_rate']}%  ·  semantic {post_p1['semantic_similarity']}%)"
    )
    if post_p1["missing_keywords"]:
        console.print(
            f"\n  [dim]Still missing:[/dim] [red]{', '.join(post_p1['missing_keywords'])}[/red]"
        )
    console.print()


def _print_review_summary(review: dict, is_jd: bool) -> None:
    console.print(Rule("[bold]Pass 2 Quality Review[/bold]"))
    score  = review["overall_quality_score"]
    colour = "green" if score >= 80 else "yellow" if score >= 60 else "red"
    console.print(f"  Quality score: [{colour}]{score}/100[/{colour}]")
    console.print(f"  [dim]{review['summary']}[/dim]")

    if is_jd and "ats_keyword_coverage" in review:
        cov = review["ats_keyword_coverage"]
        console.print(
            f"\n  Tier 1 coverage: [green]{cov.get('tier1_present', 0)}[/green] present  ·  "
            f"[yellow]{cov.get('tier1_partial', 0)}[/yellow] partial  ·  "
            f"[red]{cov.get('tier1_missing', 0)}[/red] missing  "
            f"(of {cov.get('tier1_total', 0)} total)"
        )
    console.print()


def _print_project_injection(reasoning: dict) -> None:
    if not reasoning:
        console.print(
            "[dim]  Projects unchanged — selected projects already match resume.[/dim]\n"
        )
        return
    console.print(Rule("[bold]Project Selection[/bold]"))
    console.print("  [green]✓[/green] Resume projects replaced with top 2 JD-matched projects:\n")
    for pid, reason in reasoning.items():
        console.print(f"  [cyan]•[/cyan] [dim]{pid}[/dim]  {reason}")
    console.print()


def _resolve_output_meta(
    template_id: str | None,
    resume_name: str | None,
) -> tuple[str, str]:
    """
    Returns (template_id, resume_name).
    Prompts interactively for any value not supplied via CLI flag.
    Runs after the approval loop so the user is not interrupted mid-review.
    """
    console.print(Rule("[bold]Output Configuration[/bold]"))

    if not template_id:
        template_id = Prompt.ask(
            "  [bold]Template ID[/bold] [dim](resume template to use)[/dim]"
        ).strip()
        if not template_id:
            console.print("[red]Error:[/red] Template ID cannot be empty.")
            raise typer.Exit(1)

    if not resume_name:
        resume_name = Prompt.ask(
            "  [bold]Resume Name[/bold] [dim](label for this optimised version)[/dim]"
        ).strip()
        if not resume_name:
            console.print("[red]Error:[/red] Resume name cannot be empty.")
            raise typer.Exit(1)

    console.print(
        f"\n  [dim]Template:[/dim] [cyan]{template_id}[/cyan]  "
        f"[dim]Name:[/dim] [cyan]{resume_name}[/cyan]\n"
    )
    return template_id, resume_name

@app.command()
def optimize(
    jd: str = typer.Option(
        None,
        "--jd",
        help=(
            "Path to a job description .txt file. "
            "Triggers JD-based optimisation mode. "
            "Omit to run generic optimisation (default)."
        ),
    ),
    company_name: str = typer.Option(
        None,
        "--company-name",
        help="Company name for the role. Required when --jd is provided.",
    ),
    template_id: str = typer.Option(
        None,
        "--template-id",
        help="Resume template ID for the output payload. Prompted interactively if omitted.",
    ),
    resume_name: str = typer.Option(
        None,
        "--resume-name",
        help="Label for the optimised resume in the output payload. Prompted interactively if omitted.",
    ),
):
    is_jd = jd is not None

    if is_jd and not company_name:
        console.print(
            "[red]Error:[/red] --company-name is required when --jd is provided.\n"
            "[dim]Example: tailor --jd google_swe.txt --company-name Google[/dim]"
        )
        raise typer.Exit(1)

    mode_label = f"JD — {company_name}" if is_jd else "Generic"
    _print_header(mode_label)

    from pipeline.loader          import fetch_resume, fetch_projects
    from pipeline.jd_parser       import parse_jd
    from pipeline.scorer          import ats_score
    from pipeline.project_matcher import match_and_inject
    from pipeline.pass1_optimizer import run_pass1
    from pipeline.pass2_reviewer  import run_pass2
    from pipeline.approver        import run_approval_loop
    from pipeline.publisher       import publish_resume

    console.print("[cyan]→[/cyan] Fetching resume from API...")
    try:
        resume = fetch_resume()
    except Exception as e:
        console.print(f"[red]Failed to fetch resume:[/red] {e}")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Resume loaded.\n")

    jd_context = None
    baseline   = None

    if is_jd:
        # Step 2a: Parse JD
        console.print("[cyan]→[/cyan] Parsing job description...")
        try:
            jd_text    = open(jd, encoding="utf-8").read()
            jd_context = parse_jd(jd_text, resume=resume)
        except FileNotFoundError:
            console.print(f"[red]JD file not found:[/red] {jd}")
            raise typer.Exit(1)

        t1 = len(jd_context["tiers"]["tier1"])
        t2 = len(jd_context["tiers"]["tier2"])
        console.print(f"[green]✓[/green] Extracted {t1} Tier 1 and {t2} Tier 2 keywords.\n")

        baseline = ats_score(resume, jd_context["all_keywords"])
        console.print(f"[yellow]Baseline ATS score: {baseline['composite_ats_score']}[/yellow]\n")

        # Step 2b: Fetch all projects + AI project matching
        console.print("[cyan]→[/cyan] Fetching all projects and selecting best matches...")
        try:
            all_projects        = fetch_projects()
            resume, reasoning   = match_and_inject(
                resume, all_projects, jd_context, company_name
            )
        except Exception as e:
            console.print(f"[red]Project matching failed:[/red] {e}")
            raise typer.Exit(1)

        _print_project_injection(reasoning)

    console.print("[cyan]→[/cyan] Running Pass 1 (optimisation)...")
    try:
        optimized = run_pass1(resume, "jd" if is_jd else "generic", jd_context)
    except Exception as e:
        console.print(f"[red]Pass 1 failed:[/red] {e}")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Pass 1 complete.\n")

    if is_jd:
        post_p1 = ats_score(optimized, jd_context["all_keywords"])
        _print_ats_scores(baseline, post_p1)

    console.print("[cyan]→[/cyan] Running Pass 2 (quality review)...")
    try:
        review = run_pass2(resume, optimized, "jd" if is_jd else "generic", jd_context)
    except Exception as e:
        console.print(f"[red]Pass 2 failed:[/red] {e}")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Pass 2 complete.\n")

    _print_review_summary(review, is_jd)

    final = run_approval_loop(optimized, review["issues"])

    template_id, resume_name = _resolve_output_meta(template_id, resume_name)

    console.print("[cyan]→[/cyan] Publishing final resume...")
    try:
        publish_resume(
            final_resume=final,
            template_id=template_id,
            resume_name=resume_name,
            company_name=company_name,
        )
    except Exception as e:
        console.print(f"[red]Publish failed:[/red] {e}")
        raise typer.Exit(1)
    console.print("[bold green]✓ Resume published successfully.[/bold green]\n")


if __name__ == "__main__":
    app()