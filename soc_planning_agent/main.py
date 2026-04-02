"""SOC Product Planning Agent — CLI Entry Point."""
import sys
import json
import click
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich import print as rprint

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_PATH, ANTHROPIC_API_KEY, DAILY_TOPICS, WEEKLY_THEMES
from database import Database
from agent import SOCPlanningAgent
from scheduler import AgentScheduler

console = Console()


def _get_agent() -> tuple[Database, SOCPlanningAgent]:
    if not ANTHROPIC_API_KEY:
        console.print("[red]Error: ANTHROPIC_API_KEY not set. Create a .env file or set the env var.[/red]")
        sys.exit(1)
    db = Database(DB_PATH)
    agent = SOCPlanningAgent(db, ANTHROPIC_API_KEY)
    return db, agent


def _display_collection(item: dict):
    sources = json.loads(item.get("sources", "[]"))
    panel_content = item["content"]
    if sources:
        panel_content += f"\n\n📎 Sources: {', '.join(sources[:3])}"
    console.print(Panel(
        Markdown(panel_content),
        title=f"[cyan]#{item['id']} [{item['category'].upper()}] {item['topic'][:60]}[/cyan]",
        subtitle=f"[dim]{item['collected_at'][:16]}[/dim]",
        border_style="blue",
    ))


def _display_analysis(item: dict):
    console.print(Panel(
        Markdown(item["content"]),
        title=f"[green]#{item['id']} {item['title']}[/green]",
        subtitle=f"[dim]{item['analyzed_at'][:16]} | {item['analysis_type']}[/dim]",
        border_style="green",
    ))


@click.group()
def cli():
    """🔬 SOC Product Planning Agent — Market Intelligence & Analysis"""
    pass


@cli.command()
def status():
    """Show agent status and database statistics."""
    db, _ = _get_agent()
    stats = db.get_stats()

    console.print(Panel(
        f"""[bold]SOC Product Planning Agent[/bold]

📊 Database Statistics:
  • Total collections:    {stats['total_collections']}
  • Collections (7 days): {stats['collections_this_week']}
  • Total analyses:       {stats['total_analyses']}
  • Analyses (30 days):   {stats['analyses_this_month']}
  • Total feedback:       {stats['total_feedback']}
  • Product insights:     {stats['total_insights']}

📂 Database: {DB_PATH}
🤖 Model: claude-opus-4-6
""",
        title="[bold cyan]Agent Status[/bold cyan]",
        border_style="cyan",
    ))

    # Show pending insights
    insights = db.get_insights(status="open")
    if insights:
        console.print(f"\n[yellow]⚡ {len(insights)} open product insights[/yellow]")
        for ins in insights[:5]:
            priority_color = {"high": "red", "medium": "yellow", "low": "green"}.get(ins["priority"], "white")
            console.print(f"  [{priority_color}][{ins['priority'].upper()}][/{priority_color}] {ins['title'][:70]}")


@cli.command()
@click.option("--run-now", is_flag=True, help="Run collection immediately without waiting for schedule")
def collect(run_now: bool):
    """Run daily market intelligence collection."""
    db, agent = _get_agent()

    if run_now or Confirm.ask("Run daily collection now?", default=True):
        console.print("\n[cyan]🔍 Starting daily market intelligence collection...[/cyan]")
        console.print("[dim]This will search the web for 3GPP updates, market trends, and competitor info.[/dim]\n")

        with console.status("[cyan]Collecting intelligence (this may take a few minutes)...[/cyan]"):
            collection_ids = agent.collect_daily_updates()

        console.print(f"\n[green]✓ Collected {len(collection_ids)} items[/green]\n")

        # Show what was collected
        for coll_id in collection_ids:
            item = db.get_collection_by_id(coll_id)
            if item:
                console.print(f"  [dim]#{coll_id}[/dim] [{item['category'].upper()}] {item['topic'][:70]}")

        # Prompt for feedback
        if collection_ids and Confirm.ask("\nAdd feedback on this collection run?", default=False):
            comment = Prompt.ask("Your feedback")
            for cid in collection_ids:
                agent.learn_from_feedback("collection", cid, comment)
            console.print("[green]Feedback saved and will improve future collections.[/green]")


@cli.command()
@click.option("--run-now", is_flag=True, help="Run weekly analysis immediately")
def analyze(run_now: bool):
    """Run weekly cross-analysis and product planning brief."""
    db, agent = _get_agent()

    recent = db.get_recent_collections(days=7)
    if not recent:
        console.print("[yellow]⚠ No recent collections found. Run 'collect' first.[/yellow]")
        if not Confirm.ask("Run collection first?", default=True):
            return
        with console.status("[cyan]Collecting data first...[/cyan]"):
            agent.collect_daily_updates()

    console.print("\n[cyan]📊 Running weekly SOC product planning analysis...[/cyan]")
    console.print("[dim]Cross-referencing 3GPP standards, market trends, and competitor data.[/dim]\n")

    with console.status("[cyan]Analyzing (this may take several minutes)...[/cyan]"):
        analysis_id = agent.run_weekly_analysis()

    analysis = db.get_analysis_by_id(analysis_id)
    console.print(f"\n[green]✓ Analysis complete (ID: #{analysis_id})[/green]\n")
    _display_analysis(analysis)

    # Prompt for feedback
    if Confirm.ask("\nAdd your feedback/comments on this analysis?", default=False):
        comment = Prompt.ask("Your analysis feedback")
        tags_input = Prompt.ask("Tags (comma-separated, or press Enter to skip)", default="")
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        agent.learn_from_feedback("analysis", analysis_id, comment, tags)
        console.print("[green]✓ Feedback saved. The agent will learn from this for future analyses.[/green]")


@cli.command()
@click.argument("question")
def ask(question: str):
    """Ask an ad-hoc product planning question."""
    db, agent = _get_agent()

    console.print(f"\n[cyan]🤔 Researching: {question}[/cyan]\n")

    with console.status("[cyan]Searching and analyzing...[/cyan]"):
        answer = agent.ask_question(question)

    # Save as a collection for reference
    coll_id = db.save_collection(
        category="query",
        topic=question[:200],
        content=answer,
        sources=[],
    )

    console.print(Panel(
        Markdown(answer),
        title=f"[cyan]Answer (saved as #{coll_id})[/cyan]",
        border_style="cyan",
    ))

    # Feedback
    if Confirm.ask("\nWas this answer helpful? Add feedback?", default=False):
        comment = Prompt.ask("Feedback")
        agent.learn_from_feedback("collection", coll_id, comment)
        console.print("[green]✓ Feedback saved.[/green]")


@cli.command()
@click.option("--days", default=7, help="Show collections from last N days")
@click.option("--category", default=None, help="Filter by category (3gpp, market_trends, competitors, query)")
@click.option("--limit", default=10, help="Max items to show")
def show_collections(days: int, category: Optional[str], limit: int):
    """Show recent market intelligence collections."""
    db, _ = _get_agent()
    items = db.get_recent_collections(days=days, category=category)

    if not items:
        console.print("[yellow]No collections found.[/yellow]")
        return

    console.print(f"\n[bold]Recent Collections (last {days} days)[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", width=6)
    table.add_column("Date", width=12)
    table.add_column("Category", width=14)
    table.add_column("Topic", width=50)

    for item in items[:limit]:
        table.add_row(
            str(item["id"]),
            item["collected_at"][:10],
            item["category"],
            item["topic"][:48],
        )

    console.print(table)

    if Confirm.ask("\nView a specific collection?", default=False):
        coll_id = int(Prompt.ask("Enter collection ID"))
        item = db.get_collection_by_id(coll_id)
        if item:
            _display_collection(item)
            if Confirm.ask("Add feedback on this item?", default=False):
                comment = Prompt.ask("Feedback")
                db, agent = _get_agent()
                agent.learn_from_feedback("collection", coll_id, comment)
                console.print("[green]✓ Feedback saved.[/green]")


@cli.command()
@click.option("--days", default=30, help="Show analyses from last N days")
def show_analyses(days: int):
    """Show recent product planning analyses."""
    db, _ = _get_agent()
    items = db.get_recent_analyses(days=days)

    if not items:
        console.print("[yellow]No analyses found.[/yellow]")
        return

    console.print(f"\n[bold]Recent Analyses (last {days} days)[/bold]\n")

    table = Table(show_header=True, header_style="bold green")
    table.add_column("#", width=6)
    table.add_column("Date", width=12)
    table.add_column("Type", width=12)
    table.add_column("Title", width=60)

    for item in items:
        table.add_row(
            str(item["id"]),
            item["analyzed_at"][:10],
            item["analysis_type"],
            item["title"][:58],
        )

    console.print(table)

    if Confirm.ask("\nView a specific analysis?", default=False):
        analysis_id = int(Prompt.ask("Enter analysis ID"))
        item = db.get_analysis_by_id(analysis_id)
        if item:
            _display_analysis(item)
            # Show existing feedback
            feedback = db.get_feedback_for_target("analysis", analysis_id)
            if feedback:
                console.print("\n[dim]Previous feedback on this analysis:[/dim]")
                for fb in feedback:
                    console.print(f"  [dim]• {fb['comment']}[/dim]")
            if Confirm.ask("Add new feedback?", default=False):
                comment = Prompt.ask("Feedback")
                tags_input = Prompt.ask("Tags (comma-separated, or Enter to skip)", default="")
                tags = [t.strip() for t in tags_input.split(",") if t.strip()]
                db, agent = _get_agent()
                agent.learn_from_feedback("analysis", analysis_id, comment, tags)
                console.print("[green]✓ Feedback saved.[/green]")


@cli.command()
def show_insights():
    """Show open product planning insights."""
    db, _ = _get_agent()
    insights = db.get_insights(status="open")

    if not insights:
        console.print("[yellow]No open insights. Run 'analyze' to generate insights.[/yellow]")
        return

    console.print(f"\n[bold]Open Product Planning Insights[/bold]\n")

    for ins in insights:
        priority_style = {"high": "bold red", "medium": "yellow", "low": "green"}.get(ins["priority"], "white")
        console.print(Panel(
            Markdown(ins["content"]),
            title=f"[{priority_style}][{ins['priority'].upper()}][/{priority_style}] {ins['title']}",
            subtitle=f"[dim]#{ins['id']} | {ins['insight_type']} | {ins['created_at'][:10]}[/dim]",
            border_style={"high": "red", "medium": "yellow", "low": "green"}.get(ins["priority"], "white"),
        ))

    if Confirm.ask("\nMark an insight as resolved?", default=False):
        insight_id = int(Prompt.ask("Insight ID"))
        db.update_insight_status(insight_id, "resolved")
        console.print("[green]✓ Insight marked as resolved.[/green]")


@cli.command()
def show_feedback():
    """Show all recorded feedback (for transparency into agent learning)."""
    db, _ = _get_agent()
    feedback_items = db.get_all_feedback()

    if not feedback_items:
        console.print("[yellow]No feedback recorded yet.[/yellow]")
        return

    console.print(f"\n[bold]Recorded Feedback ({len(feedback_items)} items)[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", width=6)
    table.add_column("Date", width=12)
    table.add_column("Type", width=12)
    table.add_column("Target #", width=8)
    table.add_column("Comment", width=60)

    for fb in feedback_items[:30]:
        table.add_row(
            str(fb["id"]),
            fb["created_at"][:10],
            fb["target_type"],
            str(fb["target_id"]),
            fb["comment"][:58],
        )

    console.print(table)

    # Show learned preferences
    prefs = db.get_all_preferences()
    if prefs:
        console.print(f"\n[bold]Learned Preferences[/bold]")
        for k, v in prefs.items():
            console.print(f"  [cyan]{k}[/cyan]: {v}")


@cli.command()
@click.option("--key", required=True, help="Preference key (e.g., 'focus_area', 'analysis_depth')")
@click.option("--value", required=True, help="Preference value")
def set_preference(key: str, value: str):
    """Set a user preference to guide agent behavior."""
    db, agent = _get_agent()
    agent.update_preferences({key: value})
    console.print(f"[green]✓ Preference set: {key} = {value}[/green]")
    console.print("[dim]This will influence future collections and analyses.[/dim]")


@cli.command()
@click.option("--daily-time", default="08:00", help="Daily collection time (HH:MM)")
@click.option("--weekly-day", default="monday", help="Weekly analysis day")
@click.option("--weekly-time", default="09:00", help="Weekly analysis time (HH:MM)")
def run_scheduler(daily_time: str, weekly_day: str, weekly_time: str):
    """Start the automated scheduler (runs continuously)."""
    db, agent = _get_agent()

    console.print(Panel(
        f"""[bold]Automated SOC Planning Agent Scheduler[/bold]

📅 Daily collection: {daily_time}
📊 Weekly analysis: {weekly_day.capitalize()} at {weekly_time}

Press Ctrl+C to stop.
""",
        border_style="cyan",
    ))

    scheduler = AgentScheduler()

    def daily_task():
        ids = agent.collect_daily_updates()
        console.print(f"[green]Daily collection: {len(ids)} items saved[/green]")

    def weekly_task():
        analysis_id = agent.run_weekly_analysis()
        console.print(f"[green]Weekly analysis #{analysis_id} saved[/green]")

    scheduler.register_daily(daily_task, at_time=daily_time)
    scheduler.register_weekly(weekly_task, day=weekly_day, at_time=weekly_time)

    # Show next runs
    next_runs = scheduler.get_next_runs()
    console.print(f"\n[dim]Scheduled runs:[/dim]")
    for run in next_runs:
        console.print(f"  [dim]• {run}[/dim]")

    scheduler.start_background()

    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.stop()
        console.print("\n[yellow]Scheduler stopped.[/yellow]")


@cli.command()
def interactive():
    """Interactive mode — ask questions and provide feedback in a loop."""
    db, agent = _get_agent()

    console.print(Panel(
        """[bold]SOC Product Planning Agent — Interactive Mode[/bold]

Commands:
  • Type any question to research it
  • 'collect' — run daily data collection
  • 'analyze' — run weekly analysis
  • 'insights' — show open product insights
  • 'status' — show stats
  • 'feedback <id> <collection|analysis>' — add feedback
  • 'quit' or 'exit' — exit

""",
        border_style="cyan",
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("quit", "exit", "q"):
            console.print("[yellow]Goodbye![/yellow]")
            break

        elif cmd == "collect":
            with console.status("[cyan]Collecting daily intelligence...[/cyan]"):
                ids = agent.collect_daily_updates()
            console.print(f"[green]✓ Collected {len(ids)} items[/green]")

        elif cmd == "analyze":
            with console.status("[cyan]Running weekly analysis...[/cyan]"):
                analysis_id = agent.run_weekly_analysis()
            item = db.get_analysis_by_id(analysis_id)
            _display_analysis(item)

        elif cmd == "insights":
            insights = db.get_insights()
            for ins in insights[:5]:
                priority_style = {"high": "bold red", "medium": "yellow", "low": "green"}.get(ins["priority"], "white")
                console.print(f"  [{priority_style}]#{ins['id']} [{ins['priority'].upper()}][/{priority_style}] {ins['title']}")

        elif cmd == "status":
            stats = db.get_stats()
            console.print(f"Collections: {stats['total_collections']} | Analyses: {stats['total_analyses']} | Feedback: {stats['total_feedback']}")

        elif cmd.startswith("feedback "):
            parts = cmd.split()
            if len(parts) >= 3:
                try:
                    target_id = int(parts[1])
                    target_type = parts[2]
                    comment = Prompt.ask("Your feedback comment")
                    agent.learn_from_feedback(target_type, target_id, comment)
                    console.print("[green]✓ Feedback saved.[/green]")
                except ValueError:
                    console.print("[red]Usage: feedback <id> <collection|analysis>[/red]")

        else:
            with console.status("[cyan]Researching...[/cyan]"):
                answer = agent.ask_question(user_input)
            coll_id = db.save_collection(
                category="query",
                topic=user_input[:200],
                content=answer,
                sources=[],
            )
            console.print(Panel(
                Markdown(answer),
                title=f"[cyan]Answer (#{coll_id})[/cyan]",
                border_style="cyan",
            ))
            if Confirm.ask("Add feedback on this answer?", default=False):
                comment = Prompt.ask("Feedback")
                agent.learn_from_feedback("collection", coll_id, comment)


if __name__ == "__main__":
    cli()
