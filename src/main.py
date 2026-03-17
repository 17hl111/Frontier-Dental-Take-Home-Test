# Summary: CLI entrypoints for running and exporting the scraper.

from __future__ import annotations

import json
import typer

from .runner import Runner

app = typer.Typer(help="Frontier Dental Safco agent-based scraper")


@app.command()
def run(
    # Optional overrides so the CLI can control run limits and behavior.
    max_products: int = typer.Option(None, help="Override max products per category"),
    max_pages: int = typer.Option(None, help="Override max pages per category"),
    disable_llm: bool = typer.Option(False, help="Disable ChatGPT normalization fallback"),
    headed: bool = typer.Option(False, help="Run Playwright in headed mode"),
    fresh: bool = typer.Option(False, help="Ignore old checkpoint state and start fresh"),
):
    # Run the full pipeline and print a compact stats summary as JSON.
    runner = Runner()
    stats = runner.run(
        max_products=max_products,
        max_pages=max_pages,
        disable_llm=disable_llm,
        headed=headed,
        fresh=fresh,
    )
    typer.echo(json.dumps(stats, indent=2))


@app.command()
def export():
    # Export the current database state into JSON/CSV outputs.
    runner = Runner()
    runner.export()
    typer.echo("Export complete.")


@app.command("show-stats")
def show_stats():
    # Show aggregate stats without running a new crawl.
    runner = Runner()
    typer.echo(json.dumps(runner.show_stats(), indent=2))


if __name__ == "__main__":
    app()
