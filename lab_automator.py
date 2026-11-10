"""
Dedicated High-Concurrency Labs Automator for AWS re/Start Course.
Maintains full backward-compatibility with dedicated CLI arguments while delegating
to the modular core.lab_engine.
"""

import sys
import argparse

# Enable unbuffered UTF-8 console output for Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

from core.lab_engine import run_lab_automator
from core.progress import init_labs_progress, print_labs_summary


def main():
    parser = argparse.ArgumentParser(
        description="Dedicated High-Concurrency AWS re/Start Lab Runner"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent active labs (default: 10)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of labs to execute (e.g. 5, 10 or omit for all)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Filter labs by title substring (case-insensitive)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False / headed live viewing)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset labs to pending status",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print lab progress summary and exit",
    )
    args = parser.parse_args()

    if args.status:
        tasks = init_labs_progress()
        print_labs_summary(tasks)
        return

    run_lab_automator(
        concurrency=args.concurrency,
        limit=args.limit,
        filter_text=args.filter,
        headless=args.headless,
        reset=args.reset,
    )


if __name__ == "__main__":
    main()
