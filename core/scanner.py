"""
Course Scanner and Task Extractor for AWS re/Start Course.
Discovers and classifies all course items from Canvas LMS modules into Quizzes, Labs,
and Study Materials.
"""

import time
import json
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .config import MODULES_URL, COURSE_URL, TASKS_FILE
from .auth import create_sync_browser_context, ensure_sync_canvas_login
from .progress import save_json


def scan_and_extract_tasks(headless: bool = False, force: bool = False) -> list:
    """
    Navigates to Canvas Modules page, extracts all actionable items,
    and updates extracted_tasks.json.
    """
    if TASKS_FILE.exists() and not force:
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                if isinstance(tasks, list) and len(tasks) > 0:
                    print(f"[SCANNER] Loaded existing {len(tasks)} tasks from {TASKS_FILE.name}.", flush=True)
                    return tasks
        except Exception:
            pass

    print(f"[SCANNER] Scanning course structure from {MODULES_URL}...", flush=True)

    with sync_playwright() as p:
        ctx = create_sync_browser_context(p, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        ensure_sync_canvas_login(page)
        page.goto(MODULES_URL, wait_until="networkidle", timeout=60000)
        time.sleep(3)

        html = page.content()
        ctx.close()

    soup = BeautifulSoup(html, "html.parser")
    modules = soup.select(".item-group-condensed")
    extracted = []
    task_id = 1

    for mod_idx, mod in enumerate(modules):
        mod_name_el = mod.select_one(".ig-header-title .name")
        mod_name = mod_name_el.get_text(strip=True) if mod_name_el else f"Module {mod_idx + 1}"

        current_section = "Main"
        is_instructor_led = False

        for li in mod.select("ul.ig-list > li"):
            classes = li.get("class", [])

            # Check for sub-header
            if "context_module_sub_header" in classes or "sub-header" in " ".join(classes):
                title_el = li.select_one(".title, .ig-title")
                current_section = title_el.get_text(strip=True) if title_el else li.get_text(strip=True)
                if "instructor-led" in current_section.lower():
                    is_instructor_led = True
                elif "self-study" in current_section.lower():
                    is_instructor_led = False
                continue

            if is_instructor_led:
                continue

            title_el = li.select_one(".ig-title, .title, a.title")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            title_lower = title.lower()

            # Classify task
            if "kc -" in title_lower or "knowledge check" in title_lower or "quiz" in classes:
                task_type = "quiz"
            elif "lab" in title_lower or "activity" in title_lower or "challenge" in title_lower:
                task_type = "lab"
            else:
                task_type = "study_material"

            li_id = li.get("id", "")
            item_canvas_id = (
                li_id.replace("context_module_item_", "")
                if li_id.startswith("context_module_item_")
                else ""
            )

            if item_canvas_id:
                item_url = f"{COURSE_URL}/modules/items/{item_canvas_id}"
            else:
                link_el = li.select_one("a.ig-title, a.title")
                item_url = link_el["href"] if link_el and "href" in link_el.attrs else ""
                if item_url.startswith("/"):
                    item_url = f"https://awsrestart.instructure.com{item_url}"

            completed_icon = li.select_one("i.icon-check, [title='Completed'], [aria-label='Completed']")
            is_completed = "completed_item" in classes or bool(completed_icon)

            extracted.append({
                "id": task_id,
                "module_index": mod_idx + 1,
                "module_name": mod_name,
                "section": current_section,
                "title": title,
                "item_id": item_canvas_id,
                "url": item_url,
                "classes": classes,
                "task_type": task_type,
                "completed": is_completed,
                "status": "completed" if is_completed else "pending",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            task_id += 1

    save_json(TASKS_FILE, extracted)
    print(f"[SCANNER] Successfully cataloged {len(extracted)} actionable items to {TASKS_FILE.name}.", flush=True)
    return extracted
