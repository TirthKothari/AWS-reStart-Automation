"""
AWS re/Start Complete Course Automation Suite.
Unified Master CLI for automating Knowledge Checks (quizzes), High-Concurrency Labs,
and Study Material viewing.

Usage Examples:
    # Check overall course progress dashboard
    python aws_automator.py --status
    python aws_automator.py status

    # Run Knowledge Checks (KCs) with 3 concurrent tabs (Way 1 client-side extraction)
    python aws_automator.py kc --concurrency 3 --limit 6

    # Run Labs with 10 concurrent tabs
    python aws_automator.py labs --concurrency 10 --limit 10

    # Run Study Materials with 5 concurrent tabs
    python aws_automator.py materials --concurrency 5 --limit 20

    # Filter by topic/title
    python aws_automator.py kc --filter "EC2"
    python aws_automator.py labs --filter "VPC"

    # Scan / re-scan all tasks from Canvas modules
    python aws_automator.py scan --refresh
"""

import sys
import asyncio
import argparse

# Enable unbuffered UTF-8 console output for Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

from core.config import ensure_directories
from core.progress import (
    print_master_dashboard,
    print_kc_summary,
    print_labs_summary,
    print_materials_summary,
    reset_all_progress,
)
from core.scanner import scan_and_extract_tasks
from core.kc_engine import run_kc_automator
from core.lab_engine import run_lab_automator
from core.material_engine import run_material_automator


def main():
    ensure_directories()

    parser = argparse.ArgumentParser(
        description="AWS re/Start Complete Course Automation Suite (Knowledge Checks, Labs, Study Materials)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python aws_automator.py status
  python aws_automator.py kc --concurrency 3 --limit 6
  python aws_automator.py labs --concurrency 10 --limit 10
  python aws_automator.py materials --concurrency 5 --limit 20
  python aws_automator.py scan --refresh
        """
    )

    parser.add_argument(
        "subcommand",
        nargs="?",
        default=None,
        choices=["kc", "kcs", "quiz", "quizzes", "lab", "labs", "material", "materials", "study", "scan", "status", "reset", "all"],
        help="Automation mode: kc, labs, materials, scan, status, reset, or all",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["kc", "kcs", "quiz", "quizzes", "lab", "labs", "material", "materials", "study", "scan", "status", "reset", "all"],
        help="Alternative parameter for mode",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Number of concurrent tabs (defaults: 3 for KCs, 10 for Labs, 5 for Materials)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to process in this execution",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Filter items by title substring (case-insensitive)",
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
        help="Reset progress for targeted task type back to pending",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display master progress dashboard and exit",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-scan of Canvas modules structure",
    )

    args = parser.parse_args()

    # Determine execution mode
    mode = (args.mode or args.subcommand or "").lower()

    if args.status or mode == "status":
        print_master_dashboard()
        return

    if mode == "reset":
        reset_all_progress()
        return

    if not mode:
        # Default behavior with no arguments: show dashboard and guidance
        print_master_dashboard()
        print("Tip: Specify a mode to run automation (e.g. 'python aws_automator.py kc --concurrency 3').")
        print("Run 'python aws_automator.py --help' for all options.")
        return

    # Normalize mode names
    if mode in ["kc", "kcs", "quiz", "quizzes"]:
        concurrency = args.concurrency if args.concurrency is not None else 3
        asyncio.run(
            run_kc_automator(
                concurrency=concurrency,
                limit=args.limit,
                filter_text=args.filter,
                headless=args.headless,
                reset=args.reset,
            )
        )

    elif mode in ["lab", "labs"]:
        concurrency = args.concurrency if args.concurrency is not None else 10
        run_lab_automator(
            concurrency=concurrency,
            limit=args.limit,
            filter_text=args.filter,
            headless=args.headless,
            reset=args.reset,
        )

    elif mode in ["material", "materials", "study"]:
        concurrency = args.concurrency if args.concurrency is not None else 5
        asyncio.run(
            run_material_automator(
                concurrency=concurrency,
                limit=args.limit,
                filter_text=args.filter,
                headless=args.headless,
                reset=args.reset,
            )
        )

    elif mode == "scan":
        scan_and_extract_tasks(headless=args.headless, force=args.refresh)

    elif mode == "all":
        print("[*] Starting Complete Course Automation Sequence...", flush=True)

        # 1. Study Materials
        mat_conc = args.concurrency if args.concurrency is not None else 5
        print("\n>>> Stage 1: Processing Study Materials...", flush=True)
        asyncio.run(
            run_material_automator(
                concurrency=mat_conc,
                limit=args.limit,
                filter_text=args.filter,
                headless=args.headless,
                reset=args.reset,
            )
        )

        # 2. Knowledge Checks
        kc_conc = args.concurrency if args.concurrency is not None else 3
        print("\n>>> Stage 2: Processing Knowledge Checks (Quizzes)...", flush=True)
        asyncio.run(
            run_kc_automator(
                concurrency=kc_conc,
                limit=args.limit,
                filter_text=args.filter,
                headless=args.headless,
                reset=args.reset,
            )
        )

        # 3. Labs
        lab_conc = args.concurrency if args.concurrency is not None else 10
        print("\n>>> Stage 3: Processing Labs...", flush=True)
        run_lab_automator(
            concurrency=lab_conc,
            limit=args.limit,
            filter_text=args.filter,
            headless=args.headless,
            reset=args.reset,
        )

        print("\n" + "=" * 68, flush=True)
        print("          ALL AUTOMATION STAGES COMPLETED!          ", flush=True)
        print("=" * 68, flush=True)
        print_master_dashboard()


if __name__ == "__main__":
    main()
