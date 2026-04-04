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
def collect():
    """Run daily RSS news collection (Agentic AI / Chips / Mobile / 5G CPE / CSP).

    Fetches from vetted sources: TechCrunch, DigiTimes, LightReading, EE Times, etc.
    No web search API used — fast and token-efficient.
    """
    db, agent = _get_agent()

    console.print("\n[cyan]📡 Starting daily RSS news collection...[/cyan]")
    console.print("[dim]Sources: TechCrunch, DigiTimes, LightReading, EE Times, VentureBeat, IEEE Spectrum, etc.[/dim]")
    console.print("[dim]Categories: Agentic AI / Chips & SoC / Mobile / 5G CPE / CSP Cloud[/dim]\n")

    collection_ids = agent.collect_daily_rss()

    console.print(f"\n[green]✓ Collected {len(collection_ids)} digest(s)[/green]\n")
    for coll_id in collection_ids:
        item = db.get_collection_by_id(coll_id)
        if item:
            console.print(f"  [dim]#{coll_id}[/dim] [{item['category'].upper()}] {item['topic'][:70]}")


@cli.command("collect-3gpp")
def collect_3gpp():
    """Run weekly 3GPP + vendor/operator news collection.

    Fetches from:
      - Nokia, Ericsson newsrooms (RSS, 7-day lookback)
      - Qualcomm, MediaTek press releases (RSS)
      - Major operators: Verizon, T-Mobile, Vodafone (RSS)
      - 3GPP.org spec updates (web search)
      - Targeted 3GPP Release 19/20 spec queries (web search)

    Run this once per week (e.g., every Monday).
    """
    db, agent = _get_agent()

    console.print("\n[cyan]📡 Starting weekly 3GPP & vendor/operator collection...[/cyan]")
    console.print("[dim]RSS: Nokia, Ericsson, Qualcomm, MediaTek, Verizon, T-Mobile...[/dim]")
    console.print("[dim]Web search: 3GPP specs, Release 19/20 updates, operator deployment news[/dim]\n")

    collection_ids = agent.collect_3gpp_weekly()

    console.print(f"\n[green]✓ Collected {len(collection_ids)} item(s)[/green]\n")
    for coll_id in collection_ids:
        item = db.get_collection_by_id(coll_id)
        if item:
            console.print(f"  [dim]#{coll_id}[/dim] [3GPP] {item['topic'][:70]}")


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
@click.option("--limit", default=30, help="Max items to show")
def show_collections(days: int, category: Optional[str], limit: int):
    """List recent market intelligence collections (titles only)."""
    db, _ = _get_agent()
    items = db.get_recent_collections(days=days, category=category)

    if not items:
        console.print("[yellow]No collections found.[/yellow]")
        return

    console.print(f"\n[bold]Recent Collections (last {days} days)[/bold]")
    console.print("[dim]Use: python main.py view-collection <ID>  to see full content[/dim]\n")

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("#", width=5, style="cyan")
    table.add_column("Date", width=11)
    table.add_column("Category", width=15)
    table.add_column("Topic", no_wrap=False)

    category_colors = {
        "3gpp": "green",
        "market_trends": "yellow",
        "competitors": "red",
        "query": "blue",
    }

    for item in items[:limit]:
        cat = item["category"]
        color = category_colors.get(cat, "white")
        table.add_row(
            str(item["id"]),
            item["collected_at"][:10],
            f"[{color}]{cat}[/{color}]",
            item["topic"],
        )

    console.print(table)


@cli.command()
@click.argument("collection_id", type=int)
def view_collection(collection_id: int):
    """Overview of a collection: article list with type tag and one-liner.
    Use view-article <collection_id> <num> to drill into a specific article.
    """
    db, _ = _get_agent()
    item = db.get_collection_by_id(collection_id)

    if not item:
        console.print(f"[red]Collection #{collection_id} not found.[/red]")
        return

    articles = db.get_articles_by_collection(collection_id)

    # ── New format: structured per-article ──
    if articles:
        from rich.box import SIMPLE
        table = Table(show_header=True, header_style="bold cyan", box=SIMPLE, padding=(0, 1))
        table.add_column("#",      width=3,  no_wrap=True)
        table.add_column("類型",   width=5,  no_wrap=True)
        table.add_column("標題",   min_width=30, max_width=45, no_wrap=True)
        table.add_column("一句話", min_width=25, max_width=40)

        for i, a in enumerate(articles, 1):
            atype = a.get("article_type", "info")
            if atype == "trend":
                badge = "[green]趨勢[/green]"
            elif atype == "trend_summary":
                badge = "[yellow]趨勢[/yellow]"
            else:
                badge = "[dim]資訊[/dim]"
            table.add_row(
                str(i),
                badge,
                a["title"][:43],
                (a["one_liner"] or "[dim]—[/dim]")[:38],
            )

        n_trend = sum(1 for a in articles if a["article_type"] == "trend")
        console.print(Panel(
            table,
            title=f"[cyan]#{item['id']} [{item['category'].upper()}] {item['topic']}[/cyan]",
            subtitle=f"[dim]{item['collected_at'][:16]} | {len(articles)} 篇  {n_trend} 趨勢類[/dim]",
            border_style="blue",
        ))
        console.print(
            f"\n[dim]深度分析：python main.py view-article {collection_id} <#>[/dim]"
        )

    # ── Old format: plain text content ──
    else:
        sources = json.loads(item.get("sources", "[]"))
        console.print(Panel(
            Markdown(item["content"]),
            title=f"[cyan]#{item['id']} [{item['category'].upper()}] {item['topic']}[/cyan]",
            subtitle=f"[dim]{item['collected_at'][:16]}[/dim]",
            border_style="blue",
        ))
        if sources:
            console.print("\n[bold]📎 資料來源連結[/bold]")
            for i, url in enumerate(sources, 1):
                console.print(f"  {i}. [link={url}]{url}[/link]")

    # Show feedback
    feedback = db.get_feedback_for_target("collection", collection_id)
    if feedback:
        console.print("\n[dim]已記錄的評語：[/dim]")
        for fb in feedback:
            console.print(f"  [dim]• {fb['created_at'][:10]} — {fb['comment']}[/dim]")


@cli.command()
@click.argument("collection_id", type=int)
@click.argument("article_num", type=int)
def view_article(collection_id: int, article_num: int):
    """View full detail of one article: original text + deep analysis + link.

    COLLECTION_ID  — collection number (from show-collections)
    ARTICLE_NUM    — article number within the collection (from view-collection)
    """
    db, _ = _get_agent()
    articles = db.get_articles_by_collection(collection_id)

    if not articles:
        console.print(f"[red]No articles found for collection #{collection_id}.[/red]")
        console.print("[dim]This collection uses the old format. Use view-collection instead.[/dim]")
        return

    if article_num < 1 or article_num > len(articles):
        console.print(f"[red]Article #{article_num} not found. Range: 1–{len(articles)}[/red]")
        return

    a = articles[article_num - 1]
    url = a.get("url", "")
    is_trend = a["article_type"] == "trend"

    # Header
    badge = "[green]趨勢類[/green]" if is_trend else "[dim]資訊類[/dim]"
    console.print(Panel(
        f"{badge}  [bold]{a['title']}[/bold]\n"
        f"[dim]{a.get('source','')} · {a.get('published','')[:10]}[/dim]",
        border_style="green" if is_trend else "dim",
    ))

    # Clickable link
    if url:
        console.print(f"\n🔗 [link={url}]{url}[/link]\n")

    if is_trend:
        # Original text excerpt
        full_text = a.get("full_text", "").strip()
        if full_text:
            console.print(Panel(
                full_text[:1500] + ("…" if len(full_text) > 1500 else ""),
                title="[yellow]原文摘錄[/yellow]",
                border_style="yellow",
            ))
        else:
            rss = a.get("rss_summary", "").strip()
            if rss:
                console.print(Panel(rss, title="[yellow]RSS 摘要（全文未取得）[/yellow]", border_style="yellow"))

        # Deep analysis
        analysis = a.get("analysis", "").strip()
        if analysis:
            console.print(Panel(
                Markdown(analysis),
                title="[cyan]深度分析[/cyan]",
                border_style="cyan",
            ))
        else:
            console.print("[dim]（此文章尚無深度分析）[/dim]")
    else:
        # Info article: just show one-liner + RSS summary
        one_liner = a.get("one_liner", "")
        rss = a.get("rss_summary", "").strip()
        console.print(f"[dim]資訊類文章，不做深度分析。[/dim]\n")
        if one_liner:
            console.print(f"要點：{one_liner}\n")
        if rss:
            console.print(Panel(rss, title="[dim]RSS 摘要[/dim]", border_style="dim"))



@cli.command()
@click.argument("collection_id", type=int, required=False)
@click.option("--all", "reanalyze_all", is_flag=True, help="Reanalyze all recent trend articles")
@click.option("--days", default=7, help="Days range when using --all")
def reanalyze(collection_id: int, reanalyze_all: bool, days: int):
    """Re-run deep analysis on existing articles using the latest framework.

    Uses stored full_text — no RSS re-fetch needed.

    \b
    Examples:
      python main.py reanalyze 15          # one collection
      python main.py reanalyze --all       # all recent collections
    """
    import anthropic as _anthropic
    import time as _time
    from github_collector import analyze_trend_article as _analyze

    db, _ = _get_agent()

    targets = []
    if reanalyze_all:
        targets = db.get_recent_collections(days=days)
    elif collection_id:
        item = db.get_collection_by_id(collection_id)
        if not item:
            console.print(f"[red]Collection #{collection_id} not found.[/red]")
            return
        targets = [item]
    else:
        console.print("[red]Specify a collection ID or --all.[/red]")
        return

    client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    total_updated = 0

    for item in targets:
        coll_id = item["id"]
        articles = db.get_articles_by_collection(coll_id)
        if not articles:
            console.print(f"  [dim]#{coll_id} skipped (old format)[/dim]")
            continue

        trend_arts = [a for a in articles if a.get("article_type") == "trend"]
        if not trend_arts:
            console.print(f"  [dim]#{coll_id} [{item['category']}] — no trend articles[/dim]")
            continue

        console.print(f"\n[cyan]#{coll_id} [{item['category'].upper()}] — {len(trend_arts)} trend articles[/cyan]")

        for a in trend_arts:
            console.print(f"  ✍  {a['title'][:70]}")
            # Build article dict compatible with analyze_trend_article
            art_dict = {
                "title":     a["title"],
                "url":       a["url"],
                "source":    a["source"],
                "published": a["published"],
                "summary":   a["rss_summary"],
                # Use stored full_text if available, skip HTTP fetch
                "_stored_full_text": a.get("full_text") or a.get("rss_summary", ""),
            }
            # Patch: override fetch with stored text
            body = art_dict["_stored_full_text"][:2500]
            # Call analysis prompt directly (reuse logic from github_collector)
            from github_collector import (
                COLLECTION_MODEL, MAX_ARTICLE_CHARS,
            )
            import anthropic as _anth

            prompt_parts = _build_analysis_prompt(art_dict, body)
            try:
                resp = client.messages.create(
                    model=COLLECTION_MODEL,
                    max_tokens=2000,
                    system=(
                        "You are a SoC product planning expert. Be concise and evidence-based. "
                        "CRITICAL RULE: Never fabricate numbers, statistics, or percentages. "
                        "Only cite figures that appear verbatim in the provided article text. "
                        "If no data exists in the article, write exactly '（原文未提及）'. "
                        "Empty fields are acceptable."
                    ),
                    messages=[{"role": "user", "content": prompt_parts}],
                )
                new_analysis = resp.content[0].text.strip()
                # Update DB
                with db._connect() as conn:
                    conn.execute(
                        "UPDATE articles SET analysis=? WHERE id=?",
                        (new_analysis, a["id"]),
                    )
                console.print(f"    [green]✓[/green] updated ({len(new_analysis)} chars)")
                total_updated += 1
            except Exception as e:
                console.print(f"    [red]✗ {e}[/red]")
            _time.sleep(3)

    console.print(f"\n[green]✓ Reanalyzed {total_updated} articles[/green]")
    if total_updated:
        console.print("[dim]Run 'python main.py export-html --all' to regenerate HTML.[/dim]")


def _build_analysis_prompt(article: dict, body: str) -> str:
    """Build the 4-layer analysis prompt (shared by reanalyze and github_collector)."""
    return (
        f"Article: {article['title']}\n"
        f"Source: {article.get('source','')} | Published: {article.get('published','')}\n"
        f"URL: {article.get('url','')}\n\n"
        f"Content:\n{body}\n\n"
        f"This article represents a BREAKTHROUGH or INNOVATIVE development. "
        f"Apply the 4-layer strategic analysis framework in Traditional Chinese "
        f"(keep English technical terms). Follow EXACTLY this structure:\n\n"
        f"⚠️ EMPTY FIELD RULE: If the article does not contain enough information "
        f"to answer a specific field, write EXACTLY '（原文未提及）' for that field. "
        f"Never fabricate, infer, or hallucinate content to fill gaps. "
        f"It is perfectly acceptable to have empty fields.\n\n"
        f"## 啟動層：趨勢 → 市場新機會\n"
        f"**產業趨勢**：哪些技術突破或典範轉移正在發生？（從原文找依據）\n"
        f"**市場新機會**：這個趨勢打破了哪個現有市場平衡？創造了什麼尚未被滿足的新機會？\n\n"
        f"## 鎖定層：機會 → 目標客群與痛點\n"
        f"**目標客群**：在這個新機會中，誰是最核心的目標客群？（直接客戶 vs 終端用戶）\n"
        f"**最急迫的痛點**：他們目前最急迫的問題是什麼？\n"
        f"**現有方案的不足**：為什麼現有解決方案無法解決？差距在哪裡？\n\n"
        f"## 轉換層：痛點 → 客戶價值\n"
        f"**解決方案**：這個新產品/技術具體如何解決痛點？\n"
        f"**差異化優勢**：比競爭對手更好／更快／更便宜在哪裡？\n"
        f"**客戶價值**：為客戶創造了什麼具體可感受的價值？\n"
        f"⚠️ 數字規則：只引用原文明確出現的數字。原文無數字則定性描述。"
        f"推估須標示「（推估）」並說明依據，禁止捏造數據。\n\n"
        f"## 收成層：客戶價值 → 商業價值\n"
        f"**商業模式**：如何將客戶價值轉換成公司收入？（硬體溢價／軟體訂閱／IP授權／平台費）\n"
        f"**護城河**：什麼機制讓競爭對手難以複製？（生態綁定／技術壁壘／轉換成本／網絡效應）\n"
        f"**商業價值**：對公司財務的預期影響（ASP提升／市佔擴大／毛利改善）\n"
        f"⚠️ 同樣規則：財務數字只引原文，無原文數字則定性描述或標示「（推估）」\n\n"
        f"## 產業鏈結構圖\n"
        f"用 ASCII 畫出這個新機會涉及的產業結構，從消費端往上游延伸：\n"
        f"```\n消費者／企業\n  ↓\nOEM／平台商\n  ↓\n晶片設計\n  ↓\nFoundry\n  ↓\nIP廠商\n```\n\n"
        f"## 產業鏈誘因分析\n"
        f"| 產業層級 | 誘因來源（承接下游商業價值） | 誘因強度 | 潛在障礙／利益衝突 | 態度 |\n"
        f"|---------|--------------------------|--------|-----------------|------|\n"
        f"誘因強度：🔴高 🟡中 🟢低\n"
        f"態度：積極主導 / 積極支持 / 觀望 / 被動跟進 / 抵制\n\n"
        f"最後補充：破壞性分析、既有廠商態度、新進入者機會窗口。\n"
    )


@cli.command()
@click.argument("collection_id", type=int, required=False)
@click.option("--all", "export_all", is_flag=True, help="Export all recent collections")
@click.option("--days", default=7, help="Days to include when using --all")
@click.option("--open", "open_browser", is_flag=True, help="Open in browser after export")
def export_html(collection_id: int, export_all: bool, days: int, open_browser: bool):
    """Export collection(s) to GitHub Pages HTML reports in docs/.

    \b
    Examples:
      python main.py export-html 11          # single collection
      python main.py export-html --all       # all collections from last 7 days
      python main.py export-html --all --open
    """
    from export_html import generate_collection_html, generate_index_html

    db, _ = _get_agent()
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    targets = []
    if export_all:
        targets = db.get_recent_collections(days=days)
    elif collection_id:
        item = db.get_collection_by_id(collection_id)
        if not item:
            console.print(f"[red]Collection #{collection_id} not found.[/red]")
            return
        targets = [item]
    else:
        console.print("[red]Specify a collection ID or use --all.[/red]")
        return

    collections_info = []
    for item in targets:
        coll_id = item["id"]
        articles = db.get_articles_by_collection(coll_id)
        if not articles:
            console.print(f"[dim]  #{coll_id} skipped (old format, no article data)[/dim]")
            continue

        html = generate_collection_html(item, articles)
        date = item.get("collected_at", "")[:10]
        category = item.get("category", "unknown")
        fname = f"collection_{coll_id}_{category}_{date}.html"
        out = docs_dir / fname
        out.write_text(html, encoding="utf-8")
        console.print(f"  [green]✓[/green] {fname}")

        collections_info.append({
            "id": coll_id,
            "category": category,
            "date": date,
            "total": len(articles),
            "trend": sum(1 for a in articles if a.get("article_type") == "trend"),
            "filename": fname,
        })

    # Regenerate index page with ALL existing collection HTMLs
    existing = []
    for f in docs_dir.glob("collection_*.html"):
        parts = f.stem.split("_")
        if len(parts) >= 4:
            existing.append({
                "id": parts[1],
                "category": parts[2],
                "date": parts[3],
                "total": "—",
                "trend": "—",
                "filename": f.name,
            })
    # Merge with fresh info
    fresh_fnames = {c["filename"] for c in collections_info}
    merged = collections_info + [e for e in existing if e["filename"] not in fresh_fnames]
    index_html = generate_index_html(merged)
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    console.print(f"  [green]✓[/green] index.html updated ({len(merged)} reports)")

    pages_url = "https://johnsonlu1973.github.io/tensorflow"
    console.print(f"\n[cyan]📄 GitHub Pages URL:[/cyan] {pages_url}")
    console.print(f"[dim]After git push, reports will be live in ~30 seconds.[/dim]")

    if open_browser:
        import webbrowser
        webbrowser.open(str(docs_dir / "index.html"))


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
@click.option("--days", default=7, help="Import files from the last N days (default: 7)")
@click.option("--pull/--no-pull", default=True, help="Run git pull before importing (default: yes)")
def sync(days: int, pull: bool):
    """Import latest collections from GitHub Actions into local DB.

    \b
    Workflow:
      1. GitHub Actions fetches RSS daily → commits JSON to soc_planning_agent/data/
      2. Run this command locally to pull & import into soc_planning.db
      3. Then run 'analyze' for weekly deep analysis

    \b
    Example:
      python main.py sync          # git pull + import last 7 days
      python main.py sync --days 1 # import today only
    """
    import subprocess
    import json as _json
    from pathlib import Path
    from datetime import datetime, timedelta

    db, _ = _get_agent()
    data_dir = Path(__file__).parent / "data"

    # Step 1: git pull
    if pull:
        console.print("[dim]Running git pull...[/dim]")
        result = subprocess.run(
            ["git", "pull"],
            cwd=Path(__file__).parent.parent,
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print(f"[dim]{result.stdout.strip()}[/dim]")
        else:
            console.print(f"[yellow]⚠ git pull warning: {result.stderr.strip()}[/yellow]")

    # Step 2: find JSON files within date range
    if not data_dir.exists():
        console.print("[yellow]No data/ directory found. Has GitHub Actions run yet?[/yellow]")
        return

    cutoff = datetime.now().date() - timedelta(days=days)
    imported = 0
    skipped = 0

    json_files = sorted(data_dir.glob("*.json"), reverse=True)
    if not json_files:
        console.print("[yellow]No JSON files found in data/. Has GitHub Actions run yet?[/yellow]")
        return

    console.print(f"\n[cyan]📥 Importing collections from last {days} days...[/cyan]\n")

    for json_file in json_files:
        # Parse date from filename (YYYY-MM-DD.json or 3gpp-YYYY-MM-DD.json)
        stem = json_file.stem.replace("3gpp-", "")
        try:
            file_date = datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            continue

        if file_date < cutoff:
            continue

        try:
            data = _json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[red]  ✗ {json_file.name}: {e}[/red]")
            continue

        collections = data.get("collections", [])

        format_v2 = data.get("format_version", 1) == 2

        for item in collections:
            category = item.get("category", "unknown")
            topic    = item.get("topic", json_file.stem)
            sources  = item.get("sources", [])

            # Check for duplicates
            existing = db.get_recent_collections(days=days, category=category)
            if any(e["topic"] == topic for e in existing):
                skipped += 1
                continue

            if format_v2:
                # New format: per-article structured data
                articles = item.get("articles", [])
                if not articles:
                    continue
                # Build a plain-text summary for the collection content field
                trend_titles = [a["title"] for a in articles if a.get("article_type") == "trend"]
                content = (
                    f"{len(articles)} articles ({item.get('trend_count',0)} 趨勢類)\n"
                    + ("\n".join(f"• {t}" for t in trend_titles) if trend_titles else "（無趨勢類新聞）")
                )
                article_urls = [a.get("url","") for a in articles if a.get("url")]
                coll_id = db.save_collection(
                    category=category,
                    topic=topic,
                    content=content,
                    sources=article_urls,
                )
                # Save individual articles
                for a in articles:
                    db.save_article(
                        collection_id=coll_id,
                        category=category,
                        title=a.get("title", ""),
                        url=a.get("url", ""),
                        source=a.get("source", ""),
                        published=a.get("published", ""),
                        article_type=a.get("article_type", "info"),
                        one_liner=a.get("one_liner", ""),
                        rss_summary=a.get("rss_summary", ""),
                        full_text=a.get("full_text", ""),
                        analysis=a.get("analysis", ""),
                    )
                console.print(
                    f"  [green]✓[/green] #{coll_id} [{category}] "
                    f"{topic[:55]}  [dim]({len(articles)} articles)[/dim]"
                )
            else:
                # Old format: plain text content
                content = item.get("content", "")
                if not content:
                    continue
                coll_id = db.save_collection(
                    category=category,
                    topic=topic,
                    content=content,
                    sources=sources,
                )
                console.print(f"  [green]✓[/green] #{coll_id} [{category}] {topic[:60]}")

            imported += 1

    console.print(f"\n[green]✓ Imported {imported} collection(s)[/green]", end="")
    if skipped:
        console.print(f" [dim]({skipped} already in DB, skipped)[/dim]")
    else:
        console.print()

    if imported:
        console.print("\n[dim]Run 'python main.py analyze' for weekly deep analysis.[/dim]")


@click.option("--port", default=8080, help="Port to listen on (default: 8080)")
def serve(host: str, port: int):
    """Start webhook server to receive RSS articles from n8n.

    n8n fetches RSS → filters keywords → calls Claude → POSTs here.

    \b
    Endpoints:
      GET  /health            health check
      GET  /stats             DB statistics
      POST /ingest            raw articles (agent summarizes with Claude)
      POST /ingest/analyzed   pre-analyzed summary from n8n+Claude (cheapest)
      POST /ingest/batch      multiple categories at once

    \b
    Example n8n HTTP Request node:
      URL:    http://<this-machine-ip>:{port}/ingest/analyzed
      Method: POST
      Body:   { "category": "agentic_ai",
                "summary": "{{ $json.summary }}",
                "sources": ["https://..."],
                "article_count": 5 }
    """
    from webhook_server import run_server
    run_server(host=host, port=port)


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
        ids = agent.collect_daily_rss()
        console.print(f"[green]Daily RSS collection: {len(ids)} digest(s) saved[/green]")

    def weekly_task():
        # 3GPP + vendor/operator collection first, then cross-analysis
        ids = agent.collect_3gpp_weekly()
        console.print(f"[green]3GPP weekly collection: {len(ids)} item(s) saved[/green]")
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
