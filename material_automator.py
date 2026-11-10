"""
Dedicated Study Materials Automator for AWS re/Start Course.
Maintains dedicated CLI arguments while delegating to core.material_engine.
"""

import sys
import asyncio
import argparse

# Enable unbuffered UTF-8 console output for Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

from core.material_engine import run_material_automator
from core.progress import init_materials_progress, print_materials_summary


def main():
    parser = argparse.ArgumentParser(
        description="Dedicated AWS re/Start Study Materials Automator"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Number of concurrent tabs (default: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of study materials to process (e.g. 10, 20)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Filter materials by title substring (case-insensitive)",
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
        help="Reset study materials to pending status",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print study material progress summary and exit",
    )
    args = parser.parse_args()

    if args.status:
        items = init_materials_progress()
        print_materials_summary(items)
        return

    asyncio.run(
        run_material_automator(
            concurrency=args.concurrency,
            limit=args.limit,
            filter_text=args.filter,
            headless=args.headless,
            reset=args.reset,
        )
    )


if __name__ == "__main__":
    main()
