"""
Knowledge Check (KC) Automator Entry Point for AWS re/Start Canvas Course.
Maintains full backward-compatibility with dedicated CLI arguments while delegating
to the modular core.kc_engine.
"""

import sys
import asyncio
import argparse

# Enable unbuffered UTF-8 console output for Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

from core.kc_engine import run_kc_automator
from core.progress import init_kc_progress, print_kc_summary


def main():
    parser = argparse.ArgumentParser(
        description="Dedicated Concurrent AWS re/Start Knowledge Check (KC) Automator"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Number of concurrent KCs running in parallel (default: 3)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total number of KCs to process (e.g. 6, 10)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Filter KCs by title substring (case-insensitive)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: headed / live viewing)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all KCs to pending status",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print progress summary and exit",
    )
    args = parser.parse_args()

    if args.status:
        items = init_kc_progress()
        print_kc_summary(items)
        return

    asyncio.run(
        run_kc_automator(
            concurrency=args.concurrency,
            limit=args.limit,
            filter_text=args.filter,
            headless=args.headless,
            reset=args.reset,
        )
    )


if __name__ == "__main__":
    main()
