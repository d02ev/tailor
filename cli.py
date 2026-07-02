"""
tailor — AI-powered ATS resume optimiser

DEFAULT behaviour (no flags) → generic optimisation:
    tailor

JD-based optimisation — --jd flag triggers the full JD pipeline:
    tailor --jd google_swe.txt --company-name Google
    tailor --jd google_swe.txt --company-name Google --template-id abc123 --resume-name "Google SWE 2025"

JD-based optimisation + Cover Letter generation:
    tailor --jd google_swe.txt --company-name Google --cover-letter

--template-id and --resume-name are optional for both modes;
if omitted the CLI will prompt interactively before publishing.
--company-name is REQUIRED when --jd is provided.
--cover-letter is only valid when --jd is provided.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.prompt import Prompt

app     = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
console = Console()


# ── UI helpers ────────────────────────────────────────────────────────────────

def _print_header(mode_label: str) -> None:
    title    = Text("tailor", style="bold cyan")
    subtitle = Text(f"Mode: {mode_label}", style="dim white")
    console.print(Panel(f"{title}\n{subtitle}", border_style="cyan", padding=(0, 2)))
    console.print()


def _print_ats_scores(baseline: dict, post_p1: dict) -> dict:
    """
    Renders the ATS score comparison table and returns the score_delta dict
    so the caller can check for regressions.
    """
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
    return delta


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


def _review_final_resume(final_resume: dict) -> tuple[dict, Path]:
    from pipeline.review_checkpoint import write_review_file, load_reviewed_resume

    review_path = write_review_file(final_resume)

    console.print(Rule("[bold]Manual Resume Review[/bold]"))
    console.print(
        "  Final resume written to:\n"
        f"  [cyan]{review_path}[/cyan]\n"
        "  Edit this file, save it, then continue."
    )

    while True:
        choice = Prompt.ask(
            "  [bold]Continue to publish?[/bold] [[green]c[/green]/[red]q[/red]]",
            choices=["c", "q"],
            default="c",
            show_choices=False,
        )

        if choice == "q":
            console.print(
                f"\n[dim]Publish cancelled. Edited resume kept at {review_path}.[/dim]\n"
            )
            raise typer.Exit(0)

        try:
            reviewed_resume = load_reviewed_resume(review_path)
            return reviewed_resume, review_path
        except FileNotFoundError:
            console.print(
                f"[red]resume.json not found at:[/red] {review_path}\n"
                "[dim]Recreate it or restore the file, then continue.[/dim]"
            )
        except Exception as e:
            console.print(
                f"[red]resume.json is invalid:[/red] {e}\n"
                "[dim]Fix the JSON and continue again.[/dim]"
            )


# ── Main command ──────────────────────────────────────────────────────────────

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
    cover_letter: bool = typer.Option(
        False,
        "--cover-letter",
        is_flag=True,
        help=(
            "Generate a cover letter after optimisation. "
            "Only valid when --jd is provided. "
            "Cover letter is displayed in the terminal and saved as a .docx file."
        ),
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

    # ── Validate ──────────────────────────────────────────────────────────────
    if is_jd and not company_name:
        console.print(
            "[red]Error:[/red] --company-name is required when --jd is provided.\n"
            "[dim]Example: tailor --jd google_swe.txt --company-name Google[/dim]"
        )
        raise typer.Exit(1)

    if cover_letter and not is_jd:
        console.print(
            "[red]Error:[/red] --cover-letter requires --jd to be provided.\n"
            "[dim]Example: tailor --jd google_swe.txt --company-name Google --cover-letter[/dim]"
        )
        raise typer.Exit(1)

    mode_parts = [f"JD — {company_name}" if is_jd else "Generic"]
    if cover_letter:
        mode_parts.append("+ Cover Letter")
    _print_header("  ·  ".join(mode_parts))

    # ── Deferred imports ──────────────────────────────────────────────────────
    from pipeline.loader            import fetch_resume, fetch_projects
    from pipeline.jd_parser         import parse_jd
    from pipeline.scorer            import ats_score
    from pipeline.project_matcher   import match_and_inject
    from pipeline.pass1_optimizer   import run_pass1
    from pipeline.pass2_reviewer    import run_pass2
    from pipeline.approver          import run_approval_loop
    from pipeline.publisher         import publish_resume
    from pipeline.review_checkpoint import cleanup_review_file

    # ── Step 1: Fetch resume ──────────────────────────────────────────────────
    console.print("[cyan]→[/cyan] Fetching resume from API...")
    try:
        resume = fetch_resume()
    except Exception as e:
        console.print(f"[red]Failed to fetch resume:[/red] {e}")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Resume loaded.\n")

    # ── JD-only steps ─────────────────────────────────────────────────────────
    jd_context = None
    jd_text    = None
    baseline   = None
    post_p1    = None

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
            all_projects      = fetch_projects()
            resume, reasoning = match_and_inject(
                resume, all_projects, jd_context, company_name
            )
        except Exception as e:
            console.print(f"[red]Project matching failed:[/red] {e}")
            raise typer.Exit(1)

        _print_project_injection(reasoning)

    # ── Step 3: Pass 1 — Optimisation ────────────────────────────────────────
    console.print("[cyan]→[/cyan] Running Pass 1 (optimisation)...")
    try:
        optimized = run_pass1(resume, "jd" if is_jd else "generic", jd_context)
    except Exception as e:
        console.print(f"[red]Pass 1 failed:[/red] {e}")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Pass 1 complete.\n")

    # ── Step 3b: ATS regression check (JD mode only) ─────────────────────────
    if is_jd:
        post_p1 = ats_score(optimized, jd_context["all_keywords"])
        delta   = _print_ats_scores(baseline, post_p1)

        if delta["composite_delta"] < 0:
            console.print(
                "[bold yellow]⚠ ATS score declined after Pass 1 "
                f"({delta['composite_delta']:+.1f}).[/bold yellow]\n"
                "  The original resume already scores higher for this JD.\n"
                "  Skipping Pass 2, approval, and publish.\n"
            )

            # Still generate the cover letter if requested — it uses the
            # original resume which is the stronger version for this JD
            if cover_letter:
                from pipeline.cover_letter_generator import generate_cover_letter
                console.print(Rule("[bold]Cover Letter Generation[/bold]"))
                try:
                    generate_cover_letter(
                        resume=resume,      # original, not optimized
                        jd_text=jd_text,
                        jd_context=jd_context,
                        company_name=company_name,
                    )
                except Exception as e:
                    console.print(
                        f"[yellow]Warning:[/yellow] Cover letter generation failed: {e}\n"
                    )

            raise typer.Exit(0)

    # ── Step 4: Pass 2 — Quality review ──────────────────────────────────────
    console.print("[cyan]→[/cyan] Running Pass 2 (quality review)...")
    try:
        review = run_pass2(
            original=resume,
            optimized=optimized,
            mode="jd" if is_jd else "generic",
            jd_context=jd_context,
            ats_scores=post_p1,     # None in generic mode — scorer not run
        )
    except Exception as e:
        console.print(f"[red]Pass 2 failed:[/red] {e}")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Pass 2 complete.\n")

    _print_review_summary(review, is_jd)

    # ── Step 5: Interactive approval ──────────────────────────────────────────
    final = run_approval_loop(optimized, review["issues"])

    # ── Step 6: Cover letter generation (optional, JD mode only) ─────────────
    if cover_letter:
        from pipeline.cover_letter_generator import generate_cover_letter
        console.print(Rule("[bold]Cover Letter Generation[/bold]"))
        try:
            generate_cover_letter(
                resume=final,
                jd_text=jd_text,
                jd_context=jd_context,
                company_name=company_name,
            )
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Cover letter generation failed: {e}\n")

    # ── Step 7: Manual resume review checkpoint ───────────────────────────────
    reviewed_resume, review_path = _review_final_resume(final)

    # ── Step 8: Resolve output metadata ──────────────────────────────────────
    template_id, resume_name = _resolve_output_meta(template_id, resume_name)

    # ── Step 9: Publish ───────────────────────────────────────────────────────
    console.print("[cyan]→[/cyan] Publishing final resume...")
    try:
        publish_resume(
            final_resume=reviewed_resume,
            template_id=template_id,
            resume_name=resume_name,
            company_name=company_name,
        )
    except Exception as e:
        console.print(
            f"[red]Publish failed:[/red] {e}\n"
            f"[dim]Kept review file for retry: {review_path}[/dim]"
        )
        raise typer.Exit(1)

    try:
        cleanup_review_file(review_path)
    except Exception as e:
        console.print(
            f"[yellow]Warning:[/yellow] Published successfully, but couldn't delete "
            f"review file ({review_path}): {e}"
        )

    console.print("[bold green]✓ Resume published successfully.[/bold green]\n")


if __name__ == "__main__":
    app()