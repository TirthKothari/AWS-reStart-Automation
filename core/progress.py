"""
Progress Tracking and Dashboard Reporting for AWS re/Start Course Automation.
Maintains state in JSON files and provides formatted console summaries.
"""

import json
import time
import asyncio
from datetime import datetime
from pathlib import Path

from .config import (
    PROGRESS_KC_FILE,
    PROGRESS_LABS_FILE,
    PROGRESS_MATERIALS_FILE,
    TASKS_FILE,
)

# Async lock for thread-safe concurrent saves
_async_save_lock = asyncio.Lock()


def load_json(filepath: Path, default=None):
    """Safely loads data from a JSON file."""
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning reading {filepath.name}: {e}", flush=True)
    return default if default is not None else []


def save_json(filepath: Path, data):
    """Safely writes data to a JSON file with pretty formatting."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ==========================================
# Knowledge Checks Progress Functions
# ==========================================

def init_kc_progress():
    """Initializes or loads kc_progress.json."""
    existing = load_json(PROGRESS_KC_FILE)
    if isinstance(existing, list) and len(existing) > 0:
        return existing

    # Fallback: extract quizzes from extracted_tasks.json
    tasks = load_json(TASKS_FILE, [])
    kc_items = []
    for t in tasks:
        if t.get("task_type") == "quiz":
            kc_items.append({
                "title": t.get("title"),
                "url": t.get("url"),
                "module_name": t.get("module_name"),
                "module_index": t.get("module_index"),
                "status": "completed" if t.get("completed") else "pending",
                "score": "100/100" if t.get("completed") else "",
                "completed_at": datetime.now().isoformat() if t.get("completed") else None,
                "error": None
            })

    save_json(PROGRESS_KC_FILE, kc_items)
    return kc_items


async def update_kc_item_progress(kc_items, item, status, score="", error=None):
    """Thread-safe update of an individual KC item."""
    async with _async_save_lock:
        item["status"] = status
        item["score"] = score
        if status == "completed":
            item["completed_at"] = datetime.now().isoformat()
            item["error"] = None
        else:
            item["error"] = error
        save_json(PROGRESS_KC_FILE, kc_items)


def print_kc_summary(items):
    """Prints a structured summary of Knowledge Checks."""
    total = len(items)
    completed = len([i for i in items if i.get("status") == "completed"])
    pending = len([i for i in items if i.get("status") == "pending"])
    failed = len([i for i in items if i.get("status") == "failed"])
    in_prog = len([i for i in items if i.get("status") == "in_progress"])

    pct = (completed / total * 100) if total > 0 else 0
    print("\n" + "=" * 62, flush=True)
    print("      AWS re/Start Knowledge Checks Progress Summary", flush=True)
    print("=" * 62, flush=True)
    print(f" Total Knowledge Checks : {total}", flush=True)
    print(f" Completed (100% Score) : {completed} ({pct:.1f}%)", flush=True)
    print(f" Pending                : {pending}", flush=True)
    print(f" Failed / Needs Retry   : {failed}", flush=True)
    if in_prog > 0:
        print(f" Currently In Progress  : {in_prog}", flush=True)
    print("=" * 62 + "\n", flush=True)


# ==========================================
# Labs Progress Functions
# ==========================================

def init_labs_progress():
    """Initializes or loads course_progress.json for Labs."""
    existing = load_json(PROGRESS_LABS_FILE)
    if isinstance(existing, list) and len(existing) > 0:
        return existing

    tasks = load_json(TASKS_FILE, [])
    save_json(PROGRESS_LABS_FILE, tasks)
    return tasks


def save_labs_progress(tasks):
    """Saves updated tasks list to course_progress.json."""
    save_json(PROGRESS_LABS_FILE, tasks)


def print_labs_summary(tasks):
    """Prints a structured summary of Labs."""
    labs = [t for t in tasks if t.get("task_type") == "lab"]
    total = len(labs)
    completed = sum(1 for t in labs if t.get("completed") or t.get("status") == "completed")
    pending = total - completed

    pct = (completed / total * 100) if total > 0 else 0
    print("\n" + "=" * 62, flush=True)
    print("           AWS re/Start Labs Progress Summary", flush=True)
    print("=" * 62, flush=True)
    print(f" Total Labs             : {total}", flush=True)
    print(f" Completed Labs         : {completed} ({pct:.1f}%)", flush=True)
    print(f" Remaining Pending Labs : {pending}", flush=True)
    print("=" * 62 + "\n", flush=True)


# ==========================================
# Study Materials Progress Functions
# ==========================================

def init_materials_progress():
    """Initializes or loads material_progress.json."""
    existing = load_json(PROGRESS_MATERIALS_FILE)
    if isinstance(existing, list) and len(existing) > 0:
        return existing

    tasks = load_json(TASKS_FILE, [])
    mat_items = []
    for t in tasks:
        if t.get("task_type") == "study_material":
            mat_items.append({
                "id": t.get("id"),
                "module_index": t.get("module_index"),
                "module_name": t.get("module_name"),
                "title": t.get("title"),
                "url": t.get("url"),
                "completed": bool(t.get("completed")),
                "status": "completed" if t.get("completed") else "pending",
                "completed_at": datetime.now().isoformat() if t.get("completed") else None,
                "error": None
            })

    save_json(PROGRESS_MATERIALS_FILE, mat_items)
    return mat_items


async def update_material_item_progress(mat_items, item, status, error=None):
    """Thread-safe update of a study material item."""
    async with _async_save_lock:
        item["status"] = status
        item["completed"] = (status == "completed")
        if status == "completed":
            item["completed_at"] = datetime.now().isoformat()
            item["error"] = None
        else:
            item["error"] = error
        save_json(PROGRESS_MATERIALS_FILE, mat_items)


def print_materials_summary(items):
    """Prints a structured summary of Study Materials."""
    total = len(items)
    completed = len([i for i in items if i.get("status") == "completed" or i.get("completed")])
    pending = total - completed

    pct = (completed / total * 100) if total > 0 else 0
    print("\n" + "=" * 62, flush=True)
    print("       AWS re/Start Study Materials Progress Summary", flush=True)
    print("=" * 62, flush=True)
    print(f" Total Study Materials  : {total}", flush=True)
    print(f" Completed / Viewed     : {completed} ({pct:.1f}%)", flush=True)
    print(f" Remaining Pending      : {pending}", flush=True)
    print("=" * 62 + "\n", flush=True)


# ==========================================
# Master Overview Dashboard
# ==========================================

def print_master_dashboard():
    """Prints the comprehensive all-in-one course dashboard."""
    kcs = init_kc_progress()
    labs = [t for t in init_labs_progress() if t.get("task_type") == "lab"]
    mats = init_materials_progress()

    kc_done = len([i for i in kcs if i.get("status") == "completed"])
    kc_total = len(kcs)
    kc_pct = (kc_done / kc_total * 100) if kc_total else 0

    lab_done = sum(1 for t in labs if t.get("completed") or t.get("status") == "completed")
    lab_total = len(labs)
    lab_pct = (lab_done / lab_total * 100) if lab_total else 0

    mat_done = len([i for i in mats if i.get("status") == "completed" or i.get("completed")])
    mat_total = len(mats)
    mat_pct = (mat_done / mat_total * 100) if mat_total else 0

    total_tasks = kc_total + lab_total + mat_total
    total_completed = kc_done + lab_done + mat_done
    overall_pct = (total_completed / total_tasks * 100) if total_tasks else 0

    print("\n" + "=" * 68, flush=True)
    print("          AWS re/Start Course Automation Master Dashboard", flush=True)
    print("=" * 68, flush=True)
    print(f" Category             Completed / Total       Progress   Status", flush=True)
    print("-" * 68, flush=True)
    print(f" Knowledge Checks     {kc_done:4d} / {kc_total:4d}             {kc_pct:6.1f}%    {'COMPLETED' if kc_done == kc_total else 'IN PROGRESS'}", flush=True)
    print(f" Labs                 {lab_done:4d} / {lab_total:4d}             {lab_pct:6.1f}%    {'COMPLETED' if lab_done == lab_total else 'IN PROGRESS'}", flush=True)
    print(f" Study Materials      {mat_done:4d} / {mat_total:4d}             {mat_pct:6.1f}%    {'COMPLETED' if mat_done == mat_total else 'IN PROGRESS'}", flush=True)
    print("-" * 68, flush=True)
    print(f" OVERALL COURSE       {total_completed:4d} / {total_tasks:4d}             {overall_pct:6.1f}%    {'COMPLETE' if total_completed == total_tasks else 'IN PROGRESS'}", flush=True)
    print("=" * 68 + "\n", flush=True)
