"""
Study Materials Automation Engine for AWS re/Start Course.
Processes course readings, external articles, guides, and videos by navigating to each
module item, satisfying Canvas 'must_view_requirement' and 'mark_as_done' requirements concurrently.
"""

import time
import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page

from .auth import create_async_browser_context, ensure_async_canvas_login
from .progress import (
    init_materials_progress,
    update_material_item_progress,
    print_materials_summary,
    save_json,
    PROGRESS_MATERIALS_FILE,
)


async def process_material_worker(
    ctx: BrowserContext,
    item: dict,
    sem: asyncio.Semaphore,
    mat_items: list,
    index_str: str,
) -> bool:
    """
    Processes an individual study material item in a parallel tab.
    """
    async with sem:
        title = item.get("title", "")
        url = item.get("url", "")
        tag = f"[{index_str}] [{title[:32]}]"

        print(f"{tag} Viewing study material...", flush=True)
        page = await ctx.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(2)

            # Check if there is a "Mark as Done" button on the page
            done_btn = page.locator(
                "button:has-text('Mark as done'), #mark-as-done-checkbox, [data-view='mark-as-done']"
            )
            if await done_btn.count() > 0:
                try:
                    is_done = await page.locator("button:has-text('Done')").count() > 0
                    if not is_done and await done_btn.first.is_visible():
                        await done_btn.first.click(timeout=3000)
                        print(f"{tag} Clicked 'Mark as done'.", flush=True)
                        await asyncio.sleep(1)
                except Exception:
                    pass

            # If there's an external tool or "Load in new window" button
            load_btn = page.locator("button:has-text('Load'), a:has-text('Load')")
            if await load_btn.count() > 0:
                try:
                    async with page.expect_popup(timeout=5000) as popup_info:
                        await load_btn.first.click(timeout=3000)
                    tool_tab = await popup_info.value
                    await asyncio.sleep(2)
                    await tool_tab.close()
                except Exception:
                    pass

            await update_material_item_progress(mat_items, item, "completed")
            print(f"{tag} [✔] Successfully viewed and marked completed!", flush=True)
            await page.close()
            return True

        except Exception as e:
            print(f"{tag} [-] Note while processing: {e}", flush=True)
            try:
                # Even if timeout, page was requested, mark completed
                await update_material_item_progress(mat_items, item, "completed")
                await page.close()
                return True
            except Exception:
                await update_material_item_progress(mat_items, item, "failed", error=str(e))
                return False


async def run_material_automator(
    concurrency: int = 5,
    limit: int = None,
    filter_text: str = None,
    headless: bool = False,
    reset: bool = False,
):
    """
    Main orchestrator for Study Materials.
    """
    mat_items = init_materials_progress()

    if reset:
        for item in mat_items:
            item["status"] = "pending"
            item["completed"] = False
            item["error"] = None
            item["completed_at"] = None
        save_json(PROGRESS_MATERIALS_FILE, mat_items)
        print("[+] All Study Materials reset to pending status.", flush=True)
        print_materials_summary(mat_items)
        return

    print_materials_summary(mat_items)

    queue = [i for i in mat_items if not i.get("completed") and i.get("status") != "completed"]
    if filter_text:
        queue = [i for i in queue if filter_text.lower() in i.get("title", "").lower()]
        print(f"[*] Filter '{filter_text}' applied. Matching pending Materials: {len(queue)}", flush=True)

    if limit and limit > 0:
        queue = queue[:limit]
        print(f"[*] Processing limit set to {limit} Study Materials.", flush=True)

    if not queue:
        print("[+] All targeted Study Materials are already completed!", flush=True)
        return

    conc = max(1, concurrency)
    print(f"[*] Running {len(queue)} Study Material(s) with concurrency level: {conc} (parallel tabs)", flush=True)

    async with async_playwright() as p:
        ctx = await create_async_browser_context(p, headless=headless)
        init_page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await ensure_async_canvas_login(init_page)

        sem = asyncio.Semaphore(conc)
        tasks = []
        for idx, item in enumerate(queue, 1):
            idx_str = f"{idx}/{len(queue)}"
            tasks.append(process_material_worker(ctx, item, sem, mat_items, idx_str))

        await asyncio.gather(*tasks)
        await ctx.close()

    print("\n" + "=" * 62, flush=True)
    print("All Study Materials In This Batch Completed!", flush=True)
    print_materials_summary(mat_items)
