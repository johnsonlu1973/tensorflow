"""Scheduler for automated daily/weekly tasks."""
import schedule
import time
import threading
from datetime import datetime
from typing import Callable

from rich.console import Console

console = Console()


class AgentScheduler:
    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._daily_callbacks: list[Callable] = []
        self._weekly_callbacks: list[Callable] = []

    def register_daily(self, callback: Callable, at_time: str = "08:00"):
        """Register a daily task at specified time (HH:MM)."""
        self._daily_callbacks.append(callback)
        schedule.every().day.at(at_time).do(self._run_callback, callback, "daily")
        console.print(f"[dim]Scheduled daily task at {at_time}[/dim]")

    def register_weekly(self, callback: Callable, day: str = "monday", at_time: str = "09:00"):
        """Register a weekly task on specified day and time."""
        self._weekly_callbacks.append(callback)
        getattr(schedule.every(), day).at(at_time).do(self._run_callback, callback, "weekly")
        console.print(f"[dim]Scheduled weekly task on {day} at {at_time}[/dim]")

    def _run_callback(self, callback: Callable, task_type: str):
        console.print(f"\n[cyan]⏰ Running scheduled {task_type} task at {datetime.now().strftime('%Y-%m-%d %H:%M')}[/cyan]")
        try:
            callback()
            console.print(f"[green]✓ Scheduled {task_type} task completed[/green]")
        except Exception as e:
            console.print(f"[red]✗ Scheduled {task_type} task failed: {e}[/red]")

    def start_background(self):
        """Start scheduler in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        console.print("[green]Background scheduler started[/green]")

    def _run_loop(self):
        while self._running:
            schedule.run_pending()
            time.sleep(60)  # check every minute

    def stop(self):
        self._running = False
        schedule.clear()

    def run_now_daily(self):
        """Manually trigger daily collection immediately."""
        for cb in self._daily_callbacks:
            self._run_callback(cb, "daily (manual)")

    def run_now_weekly(self):
        """Manually trigger weekly analysis immediately."""
        for cb in self._weekly_callbacks:
            self._run_callback(cb, "weekly (manual)")

    def get_next_runs(self) -> list[str]:
        return [str(job.next_run) for job in schedule.jobs]
