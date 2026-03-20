"""CSUN Conference Analytics - Main CLI entry point.

Usage:
    uv run python main.py scrape-sessions [--year 2024] [--max N]
    uv run python main.py scrape-exhibitors [--year 2024]
    uv run python main.py analyze-sessions [--year 2024]
    uv run python main.py analyze-exhibitors [--year 2024]
    uv run python main.py scrape-all
    uv run python main.py analyze-all
    uv run python main.py normalize-topics [--force]
    uv run python main.py dashboard [--port 8050]
    uv run python main.py docs [--serve]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env files (project root relative to this file)
_root = Path(__file__).resolve().parent
load_dotenv(_root / ".env")
load_dotenv(_root / ".env.local", override=True)

from rich.console import Console
from rich.table import Table

console = Console()
DATA_DIR = Path("data")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_scrape_sessions(args: argparse.Namespace) -> None:
    from csun_analytics.models.session import save_sessions

    for year in _parse_years(args.year):
        console.print(f"\n[bold]Scraping sessions for {year}...[/bold]")

        if year in (2025, 2026):
            # Cvent-hosted conferences - sessions via GraphQL + speakers
            from csun_analytics.scrapers.cvent import CventScraper
            scraper = CventScraper(year=year)
            sessions = scraper.scrape_sessions()
            speakers = scraper.fetch_speakers()
            if speakers:
                import json as _json
                speaker_path = DATA_DIR / "raw" / f"speakers_{year}.json"
                speaker_path.parent.mkdir(parents=True, exist_ok=True)
                speaker_path.write_text(_json.dumps(
                    [{"name": p.name, "affiliation": p.affiliation, "role": p.role}
                     for p in speakers],
                    indent=2, ensure_ascii=False,
                ))
                console.print(
                    f"[green]Saved {len(speakers)} speakers to {speaker_path}[/green]"
                )
        else:
            from csun_analytics.scrapers.sessions import SessionScraper
            scraper = SessionScraper(year=year)
            sessions = scraper.scrape_all_sessions(max_sessions=args.max)

            if args.papers:
                console.print("Checking for downloadable papers...")
                scraper.find_papers(sessions)

        out_path = DATA_DIR / "raw" / f"sessions_{year}.json"
        save_sessions(sessions, out_path)
        console.print(f"[green]Saved {len(sessions)} sessions to {out_path}[/green]")


def cmd_scrape_exhibitors(args: argparse.Namespace) -> None:
    from csun_analytics.scrapers.exhibitors import ExhibitorScraper
    from csun_analytics.models.exhibitor import save_exhibitors

    for year in _parse_years(args.year):
        console.print(f"\n[bold]Scraping exhibitors for {year}...[/bold]")
        scraper = ExhibitorScraper(year=year)
        exhibitors = scraper.scrape_all_exhibitors()

        out_path = DATA_DIR / "raw" / f"exhibitors_{year}.json"
        save_exhibitors(exhibitors, out_path)
        console.print(f"[green]Saved {len(exhibitors)} exhibitors to {out_path}[/green]")


def cmd_analyze_sessions(args: argparse.Namespace) -> None:
    from csun_analytics.models.session import load_sessions
    from csun_analytics.analysis.sessions import SessionAnalyzer

    all_sessions = []
    for year in _parse_years(args.year):
        path = DATA_DIR / "raw" / f"sessions_{year}.json"
        if not path.exists():
            console.print(f"[yellow]No data for {year}. Run scrape-sessions first.[/yellow]")
            continue
        all_sessions.extend(load_sessions(path))

    if not all_sessions:
        console.print("[red]No session data found.[/red]")
        return

    analyzer = SessionAnalyzer(all_sessions)
    summary = analyzer.summary()

    console.print("\n[bold]Session Analysis Summary[/bold]")
    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    for k, v in summary.items():
        if isinstance(v, dict):
            table.add_row(k, json.dumps(v, indent=1))
        else:
            table.add_row(k, str(v))
    console.print(table)

    console.print("\n[bold]Top 15 Presenters[/bold]")
    t2 = Table()
    t2.add_column("Presenter")
    t2.add_column("Sessions")
    for name, count in analyzer.top_presenters(15):
        t2.add_row(name, str(count))
    console.print(t2)

    console.print("\n[bold]Top 15 Organizations[/bold]")
    t3 = Table()
    t3.add_column("Organization")
    t3.add_column("Presenters")
    for name, count in analyzer.top_affiliations(15):
        t3.add_row(name, str(count))
    console.print(t3)

    out_dir = DATA_DIR / "processed" / "sessions"
    analyzer.save_report(out_dir)
    console.print(f"\n[green]Reports saved to {out_dir}/[/green]")


def cmd_analyze_exhibitors(args: argparse.Namespace) -> None:
    from csun_analytics.models.exhibitor import load_exhibitors
    from csun_analytics.analysis.exhibitors import ExhibitorAnalyzer

    all_exhibitors = []
    for year in _parse_years(args.year):
        path = DATA_DIR / "raw" / f"exhibitors_{year}.json"
        if not path.exists():
            console.print(f"[yellow]No data for {year}. Run scrape-exhibitors first.[/yellow]")
            continue
        all_exhibitors.extend(load_exhibitors(path))

    if not all_exhibitors:
        console.print("[red]No exhibitor data found.[/red]")
        return

    analyzer = ExhibitorAnalyzer(all_exhibitors)
    summary = analyzer.summary()

    console.print("\n[bold]Exhibitor Analysis Summary[/bold]")
    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    for k, v in summary.items():
        table.add_row(k, str(v))
    console.print(table)

    out_dir = DATA_DIR / "processed" / "exhibitors"
    analyzer.save_report(out_dir)
    console.print(f"\n[green]Reports saved to {out_dir}/[/green]")


def cmd_normalize_topics(args: argparse.Namespace) -> None:
    from csun_analytics.analysis.normalize import run_normalization
    console.print("[bold]Running LLM-based topic normalization...[/bold]")
    run_normalization(force=args.force)
    console.print("[green]Topic normalization complete.[/green]")


def cmd_comprehensive(args: argparse.Namespace) -> None:
    from csun_analytics.analysis.comprehensive import run_comprehensive_analysis
    run_comprehensive_analysis()


def cmd_knowledge_graph(args: argparse.Namespace) -> None:
    from csun_analytics.analysis.knowledge_graph import build_knowledge_graph
    build_knowledge_graph()


def cmd_dashboard(args: argparse.Namespace) -> None:
    from csun_analytics.dashboard.app import run_dashboard
    console.print(f"[bold]Launching dashboard on port {args.port}...[/bold]")
    run_dashboard(port=args.port, debug=args.debug)


def cmd_docs(args: argparse.Namespace) -> None:
    import subprocess
    from csun_analytics.docs_builder import build_docs

    console.print("[bold]Building documentation site...[/bold]")
    build_docs()

    if args.serve:
        console.print("\n[bold]Starting mkdocs dev server...[/bold]")
        subprocess.run(["mkdocs", "serve"], check=True)
    else:
        console.print("\n[bold]Building static site...[/bold]")
        subprocess.run(["mkdocs", "build"], check=True)
        console.print("[green]Site built to site/[/green]")


def _parse_years(year_arg: str) -> list[int]:
    if year_arg == "all":
        return [2026, 2025, 2024, 2023]
    return [int(y.strip()) for y in year_arg.split(",")]


def main() -> None:
    parser = argparse.ArgumentParser(description="CSUN Conference Analytics")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("scrape-sessions", help="Scrape session data")
    p1.add_argument("--year", default="2024", help="Year(s) to scrape (e.g., 2024 or all)")
    p1.add_argument("--max", type=int, default=None, help="Max sessions to scrape")
    p1.add_argument("--papers", action="store_true", help="Download linked papers")

    p2 = sub.add_parser("scrape-exhibitors", help="Scrape exhibitor data")
    p2.add_argument("--year", default="2024", help="Year(s) to scrape")

    p3 = sub.add_parser("analyze-sessions", help="Analyze session data")
    p3.add_argument("--year", default="2024", help="Year(s) to analyze")

    p4 = sub.add_parser("analyze-exhibitors", help="Analyze exhibitor data")
    p4.add_argument("--year", default="2024", help="Year(s) to analyze")

    sub.add_parser("scrape-all", help="Scrape all available data")
    sub.add_parser("analyze-all", help="Run all analyses")

    sub.add_parser("comprehensive", help="Run comprehensive multi-year analysis")
    sub.add_parser("knowledge-graph", help="Build knowledge graph")

    p_norm = sub.add_parser("normalize-topics", help="LLM-based topic normalization")
    p_norm.add_argument("--force", action="store_true", help="Force re-normalization")

    p_dash = sub.add_parser("dashboard", help="Launch Plotly Dash dashboard")
    p_dash.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    p_dash.add_argument("--debug", action="store_true", help="Debug mode")

    p_docs = sub.add_parser("docs", help="Build mkdocs documentation site")
    p_docs.add_argument("--serve", action="store_true", help="Serve with live reload")

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "scrape-sessions": cmd_scrape_sessions,
        "scrape-exhibitors": cmd_scrape_exhibitors,
        "analyze-sessions": cmd_analyze_sessions,
        "analyze-exhibitors": cmd_analyze_exhibitors,
        "normalize-topics": cmd_normalize_topics,
        "comprehensive": cmd_comprehensive,
        "knowledge-graph": cmd_knowledge_graph,
        "dashboard": cmd_dashboard,
        "docs": cmd_docs,
    }

    if args.command in commands:
        commands[args.command](args)
    elif args.command == "scrape-all":
        args.year = "all"
        args.max = None
        args.papers = True
        cmd_scrape_sessions(args)
        args.year = "2024"
        cmd_scrape_exhibitors(args)
    elif args.command == "analyze-all":
        args.year = "all"
        cmd_analyze_sessions(args)
        args.year = "2024"
        cmd_analyze_exhibitors(args)


if __name__ == "__main__":
    main()
