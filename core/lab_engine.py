"""
High-Concurrency Labs Automation Engine for AWS re/Start Course.
Manages a multi-tab parallel pool (up to 10+ tabs simultaneously), performs Vocareum
URL rewriting (m=editor -> m=clabide), monitors AWS instance boot status, verifies submissions,
and cleanly terminates lab environments.
"""

import time
from playwright.sync_api import sync_playwright, BrowserContext, Page

from .auth import create_sync_browser_context, ensure_sync_canvas_login
from .progress import (
    init_labs_progress,
    save_labs_progress,
    print_labs_summary,
)


class LabPoolManager:
    """Manages concurrent Vocareum lab sessions in a parallel browser pool."""

    def __init__(self, max_concurrency: int = 10, headless: bool = False):
        self.max_concurrency = max_concurrency
        self.headless = headless
        self.active_labs = {}
        self.tasks = []

    def open_lab_into_pool(self, context: BrowserContext, task: dict) -> bool:
        """Launches a new lab into the active concurrent pool."""
        task_id = task.get("id", task.get("item_id", "0"))
        title = task.get("title", "")
        url = task.get("url", "")

        print(f"[POOL +] Launching Lab #{task_id}: '{title[:32]}'...", flush=True)
        canvas_page = context.new_page()

        try:
            canvas_page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(2)

            if "login" in canvas_page.url.lower():
                print(f"[POOL] Re-authenticating for Lab #{task_id}...", flush=True)
                ensure_sync_canvas_login(canvas_page)
                canvas_page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(2)

            tool_frame = None
            for f in canvas_page.frames:
                if "tool_launch" in f.url:
                    tool_frame = f
                    break

            if not tool_frame:
                try:
                    canvas_page.wait_for_selector("iframe", timeout=10000)
                    for f in canvas_page.frames:
                        if "tool_launch" in f.url:
                            tool_frame = f
                            break
                except Exception:
                    pass

            load_btn = (
                tool_frame.locator("button:has-text('Load'), button[type='submit']")
                if tool_frame
                else canvas_page.locator("button:has-text('Load'), a:has-text('Load')")
            )

            if load_btn.count() == 0:
                print(f"[POOL] Warning: No Load button found for Lab #{task_id}. Skipping.", flush=True)
                canvas_page.close()
                return False

            with context.expect_page(timeout=30000) as new_page_info:
                load_btn.first.click()

            lab_tab = new_page_info.value
            lab_tab.wait_for_load_state("domcontentloaded", timeout=60000)
            time.sleep(3)

            # Close Canvas page to keep tab pool minimal
            try:
                canvas_page.close()
            except Exception:
                pass

            # Rewrite m=editor URL to m=clabide
            current_url = lab_tab.url
            if "m=editor" in current_url:
                clabide_url = current_url.replace("m=editor", "m=clabide")
                print(f"[LAB #{task_id}] Switching URL: m=editor -> m=clabide", flush=True)
                lab_tab.goto(clabide_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(4)

            # Check if ready or click Start Lab
            vmstatus = lab_tab.locator("#vmstatus")
            clabstatus = lab_tab.locator("#clabstatus")
            cls = vmstatus.get_attribute("class") or "" if vmstatus.count() > 0 else ""
            txt = clabstatus.inner_text().strip() if clabstatus.count() > 0 else ""

            is_ready = ("led-green" in cls) or ("ready" in txt.lower())

            if not is_ready:
                start_btn = lab_tab.locator("#launchclabsbtn")
                if start_btn.count() > 0:
                    start_btn.click()
                    print(f"[LAB #{task_id}] Clicked 'Start Lab' -> Booting AWS environment.", flush=True)
                task["status"] = "started"
            else:
                print(f"[LAB #{task_id}] Already READY (Green circle)!", flush=True)
                task["status"] = "processing"

            task["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_labs_progress(self.tasks)

            self.active_labs[task_id] = {
                "task": task,
                "tab": lab_tab,
                "start_time": time.time(),
                "status": task["status"],
            }
            print(f"[POOL] Active labs running: {len(self.active_labs)} / {self.max_concurrency}\n", flush=True)
            return True

        except Exception as e:
            print(f"[POOL] Failed to launch Lab #{task_id}: {e}", flush=True)
            try:
                canvas_page.close()
            except Exception:
                pass
            task["status"] = "failed"
            save_labs_progress(self.tasks)
            return False

    def process_active_labs_tick(self):
        """Polls active tabs in the pool, executes submissions, and ends completed sessions."""
        finished_ids = []

        for task_id, info in list(self.active_labs.items()):
            task = info["task"]
            tab = info["tab"]
            start_time = info["start_time"]
            elapsed = int(time.time() - start_time)

            try:
                # Keep URL on m=clabide
                if "m=editor" in tab.url:
                    clabide_url = tab.url.replace("m=editor", "m=clabide")
                    print(f"[LAB #{task_id}] Switching URL: m=editor -> m=clabide", flush=True)
                    tab.goto(clabide_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)

                vmstatus = tab.locator("#vmstatus")
                clabstatus = tab.locator("#clabstatus")
                cls = vmstatus.get_attribute("class") or "" if vmstatus.count() > 0 else ""
                txt = clabstatus.inner_text().strip() if clabstatus.count() > 0 else ""

                is_ready = ("led-green" in cls) or ("ready" in txt.lower())

                if is_ready:
                    print(f"\n>>> [LAB #{task_id}] READY (Green Circle after {elapsed}s)! Submitting...", flush=True)

                    # 1. Submit Assignment
                    submit_btn = tab.locator("#btn-submitasn")
                    if submit_btn.count() > 0:
                        submit_btn.click()
                        time.sleep(2)
                        yes_btn = tab.locator(".modal:visible .btn:has-text('Yes'), .bootbox:visible .btn:has-text('Yes'), a:has-text('Yes'):visible")
                        if yes_btn.count() > 0:
                            yes_btn.first.click()
                            print(f"[LAB #{task_id}] Clicked Yes on Submit dialog.", flush=True)

                            # Verify submission with Vocareum server
                            verify_start = time.time()
                            verified = False
                            while time.time() - verify_start < 45:
                                time.sleep(2)
                                in_prog = tab.evaluate("() => typeof submit_in_progress !== 'undefined' ? submit_in_progress : false")
                                btn_html = submit_btn.inner_html() if submit_btn.count() > 0 else ""
                                spinning = ("icon-spin" in btn_html) or ("Submitting" in (submit_btn.inner_text() if submit_btn.count() > 0 else ""))
                                gritter = tab.locator(".gritter-item:has-text('Submission'), .gritter-item:has-text('Submitted')")

                                if gritter.count() > 0 or (not in_prog and not spinning):
                                    verified = True
                                    print(f"[LAB #{task_id}] >>> SUBMISSION VERIFIED by server! <<<", flush=True)
                                    break

                            if not verified:
                                print(f"[LAB #{task_id}] Submit wait reached 45s timeout. Proceeding to end.", flush=True)

                    # 2. End Lab Environment
                    print(f"[LAB #{task_id}] Ending lab session...", flush=True)
                    end_btn = tab.locator("#endclabsbtn")
                    if end_btn.count() > 0:
                        end_btn.click()
                        time.sleep(2)
                        end_yes = tab.locator(".modal:visible .btn:has-text('Yes'), .bootbox:visible .btn:has-text('Yes'), a:has-text('Yes'):visible")
                        if end_yes.count() > 0:
                            end_yes.first.click()
                            print(f"[LAB #{task_id}] Confirmed End Lab dialog.", flush=True)
                            time.sleep(3)

                    # 3. Close tab & mark completed
                    tab.close()
                    task["status"] = "completed"
                    task["completed"] = True
                    task["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    save_labs_progress(self.tasks)
                    finished_ids.append(task_id)
                    print(f"[LAB #{task_id}] [COMPLETED] Lab successfully submitted and ended!\n", flush=True)

                elif elapsed > 600:  # 10 min timeout
                    print(f"[LAB #{task_id}] [TIMEOUT] Timed out waiting for AWS instance after {elapsed}s.", flush=True)
                    tab.close()
                    task["status"] = "timeout"
                    save_labs_progress(self.tasks)
                    finished_ids.append(task_id)

            except Exception as e:
                print(f"[LAB #{task_id}] Error in poll tick: {e}", flush=True)

        for tid in finished_ids:
            if tid in self.active_labs:
                del self.active_labs[tid]


def run_lab_automator(
    concurrency: int = 10,
    limit: int = None,
    filter_text: str = None,
    headless: bool = False,
    reset: bool = False,
):
    """
    Main orchestrator for High-Concurrency Labs.
    """
    tasks = init_labs_progress()

    if reset:
        for t in tasks:
            if t.get("task_type") == "lab":
                t["status"] = "pending"
                t["completed"] = False
                t["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_labs_progress(tasks)
        print("[+] All Labs reset to pending status.", flush=True)
        print_labs_summary(tasks)
        return

    print_labs_summary(tasks)

    pending_labs = [
        t for t in tasks
        if t.get("task_type") == "lab" and not t.get("completed") and t.get("status") != "completed"
    ]

    if filter_text:
        pending_labs = [t for t in pending_labs if filter_text.lower() in t.get("title", "").lower()]
        print(f"[*] Filter '{filter_text}' applied. Matching pending Labs: {len(pending_labs)}", flush=True)

    if limit and limit > 0:
        pending_labs = pending_labs[:limit]
        print(f"[*] Processing limit set to {limit} Labs.", flush=True)

    if not pending_labs:
        print("[+] All targeted Labs are already completed!", flush=True)
        return

    conc = max(1, concurrency)
    print(f"[*] Running {len(pending_labs)} Lab(s) with concurrency level: {conc} (parallel tabs)", flush=True)

    manager = LabPoolManager(max_concurrency=conc, headless=headless)
    manager.tasks = tasks

    with sync_playwright() as p:
        ctx = create_sync_browser_context(p, headless=headless)
        main_page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ensure_sync_canvas_login(main_page)

        queue = list(pending_labs)
        last_status_print = time.time()

        while queue or manager.active_labs:
            # 1. Fill pool if capacity allows
            if queue and len(manager.active_labs) < manager.max_concurrency:
                next_task = queue.pop(0)
                manager.open_lab_into_pool(ctx, next_task)

            # 2. Advance active labs
            if manager.active_labs:
                manager.process_active_labs_tick()

            # 3. Status tick every 30s
            if time.time() - last_status_print > 30:
                active_ids = list(manager.active_labs.keys())
                print(f"[STATUS TICK] Active labs ({len(active_ids)}/{manager.max_concurrency}): {active_ids} | In Queue: {len(queue)}", flush=True)
                last_status_print = time.time()

            time.sleep(2)

        ctx.close()

    print("\n" + "=" * 62, flush=True)
    print("All Labs In This Batch Completed!", flush=True)
    print_labs_summary(tasks)
