"""This module exists to provide a CLI entry point for running and exporting the scraper. It wires command line options into the Runner without exposing internal details. Possible improvement: add richer subcommands and exit codes, but that was not prioritized."""

from __future__ import annotations

import json
import argparse

from .runner import Runner

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Frontier Dental Safco agent-based scraper",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the scraper")
    run_parser.add_argument("--max-products", type=int, default=None, help="Override max products per category")
    run_parser.add_argument("--max-pages", type=int, default=None, help="Override max pages per category")
    run_parser.add_argument("--disable-llm", action="store_true", help="Disable ChatGPT normalization fallback")
    run_parser.add_argument("--headed", action="store_true", help="Run Playwright in headed mode")
    run_parser.add_argument("--fresh", action="store_true", help="Ignore old checkpoint state and start fresh")

    subparsers.add_parser("export", help="Export current database state to JSON/CSV")
    subparsers.add_parser("show-stats", help="Show aggregate stats without running a crawl")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        runner = Runner()
        stats = runner.run(
            max_products=args.max_products,
            max_pages=args.max_pages,
            disable_llm=args.disable_llm,
            headed=args.headed,
            fresh=args.fresh,
        )
        print(json.dumps(stats, indent=2))
        return

    if args.command == "export":
        runner = Runner()
        runner.export()
        print("Export complete.")
        return

    if args.command == "show-stats":
        runner = Runner()
        print(json.dumps(runner.show_stats(), indent=2))
        return


if __name__ == "__main__":
    main()
