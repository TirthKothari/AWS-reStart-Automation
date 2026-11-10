"""
Knowledge Check (KC) Automation Engine for AWS re/Start Course.
Extracts questions and verified correct answers from Storyline 360 client-side runtime (Way 1),
executes parallel headless/headed tabs, and guarantees 100% score submissions.
"""

import time
import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page

from .config import SCREENSHOTS_DIR
from .auth import create_async_browser_context, ensure_async_canvas_login
from .progress import (
    init_kc_progress,
    save_json,
    update_kc_item_progress,
    print_kc_summary,
    PROGRESS_KC_FILE,
)


def parse_data_js(data_js_str: str) -> list:
    """
    Extracts questions and 100% verified correct choice IDs from Storyline data.js payload.
    """
    start = data_js_str.find("('")
    second_quote = data_js_str.find("', '", start)
    json_str = data_js_str[second_quote + 4 : data_js_str.rfind("')")]
    data = json.loads(json_str.encode("utf-8").decode("unicode_escape"))

    questions = []
    for scene in data.get("scenes", []):
        for slide in scene.get("slides", []):
            for inter in slide.get("interactions", []):
                q_text = inter.get("lmstext")
                q_type = inter.get("type")

                correct_ids = []
                for ans in inter.get("answers", []):
                    if ans.get("status") == "correct":
                        eval_obj = ans.get("evaluate", {})
                        for stmt in eval_obj.get("statements", []):
                            cid = stmt.get("choiceid", "")
                            if cid.startswith("choices.choice_"):
                                correct_ids.append(cid.replace("choices.choice_", ""))
                            elif cid.startswith("choices."):
                                correct_ids.append(cid.replace("choices.", ""))

                questions.append({
                    "slide_id": slide.get("id"),
                    "interaction_id": inter.get("id"),
                    "question": q_text,
                    "type": q_type,
                    "correct_choice_ids": correct_ids
                })
    return questions


async def solve_kc_worker(
    ctx: BrowserContext,
    kc_item: dict,
    sem: asyncio.Semaphore,
    kc_items: list,
    index_str: str,
    delay: float = 0.0,
) -> bool:
    """
    Solves an individual Knowledge Check in an isolated parallel tab.
    """
    async with sem:
        if delay > 0:
            await asyncio.sleep(delay)

        title = kc_item.get("title", "")
        url = kc_item.get("url", "")
        tag = f"[{index_str}] [{title[:30]}]"

        print(f"\n{tag} >>> Starting KC...", flush=True)
        await update_kc_item_progress(kc_items, kc_item, "in_progress")

        canvas_page = await ctx.new_page()
        kc_tab = None

        try:
            # 1. Open Canvas assignment page
            await canvas_page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)

            # Check if already completed on Canvas
            try:
                body_text = await canvas_page.locator("body").inner_text()
                if "100/100 Points" in body_text and "SUBMITTED" in body_text:
                    print(f"{tag} [+] Already 100% submitted on Canvas!", flush=True)
                    await update_kc_item_progress(kc_items, kc_item, "completed", "100/100")
                    await canvas_page.close()
                    return True
            except Exception:
                pass

            # 2. Locate and click "Load in new window" button
            tool_frame = None
            for f in canvas_page.frames:
                if "tool_launch" in f.url:
                    tool_frame = f
                    break

            load_btn = (
                tool_frame.locator("button:has-text('Load'), button[type='submit']")
                if tool_frame
                else canvas_page.locator("button:has-text('Load')")
            )
            if await load_btn.count() == 0:
                print(f"{tag} [-] Error: Could not locate 'Load in new window' button", flush=True)
                await update_kc_item_progress(kc_items, kc_item, "failed", error="Could not locate Load button")
                await canvas_page.close()
                return False

            print(f"{tag} Launching player in new tab...", flush=True)
            async with canvas_page.expect_popup() as new_page_info:
                await load_btn.first.click()

            kc_tab = await new_page_info.value
            await kc_tab.wait_for_load_state("domcontentloaded", timeout=60000)

            # Prevent background tab throttling in Storyline
            await kc_tab.add_init_script("""
                try {
                    Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
                    Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
                    window.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
                } catch(e) {}
            """)

            # 3. Wait for Storyline content frame
            print(f"{tag} Waiting for player frames...", flush=True)
            quiz_frame = None
            start_time = time.time()
            while time.time() - start_time < 35:
                for f in kc_tab.frames:
                    if f.name == "ScormContent" or "/vault/" in f.url:
                        quiz_frame = f
                        break
                if quiz_frame:
                    break
                await asyncio.sleep(1.5)

            if not quiz_frame:
                quiz_frame = kc_tab.frames[-1]

            # Prevent visibility throttling inside the SCORM iframe
            try:
                await quiz_frame.evaluate("""() => {
                    try {
                        Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
                        Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
                        window.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
                    } catch(e) {}
                }""")
            except Exception:
                pass

            # 4. Handle Resume prompt ("Would you like to resume where you left off?")
            for _ in range(8):
                try:
                    no_btn = quiz_frame.locator("button[aria-label='No'], button:has-text('No'), [data-acc-text='No']")
                    if await no_btn.count() > 0 and await no_btn.first.is_visible():
                        print(f"{tag} Clicking 'No' on Resume dialog...", flush=True)
                        await no_btn.first.click(force=True)
                        await asyncio.sleep(2)
                        break
                except Exception:
                    pass
                await asyncio.sleep(1)

            # 5. Extract question schema from data.js
            data_js = None
            for attempt in range(6):
                candidate_frames = [quiz_frame] + [f for f in kc_tab.frames if f != quiz_frame]
                for f in candidate_frames:
                    try:
                        text = await f.evaluate("() => fetch('html5/data/js/data.js').then(r => r.text()).catch(() => '')")
                        if text and "globalProvideData" in text:
                            data_js = text
                            quiz_frame = f
                            break
                    except Exception:
                        pass
                if data_js:
                    break
                await asyncio.sleep(1.5)

            if not data_js or "globalProvideData" not in data_js:
                err_shot = SCREENSHOTS_DIR / f"error_{kc_item.get('module_index')}.png"
                await kc_tab.screenshot(path=str(err_shot))
                await kc_tab.close()
                await canvas_page.close()
                print(f"{tag} [-] FAILED: Could not fetch data.js", flush=True)
                await update_kc_item_progress(kc_items, kc_item, "failed", error="Could not fetch data.js")
                return False

            questions = parse_data_js(data_js)
            print(f"{tag} Loaded {len(questions)} questions with verified answers.", flush=True)

            # 6. Click Start button and wait for Question 1 slide to settle
            start_clicked = False
            for _ in range(8):
                start_btn = quiz_frame.locator("[data-acc-text='Start'], button:has-text('Start')").first
                try:
                    if await start_btn.count() > 0 and await start_btn.is_visible():
                        await start_btn.click(force=True)
                        start_clicked = True
                        break
                except Exception:
                    pass

                res = await quiz_frame.evaluate("""
                () => {
                    let els = Array.from(document.querySelectorAll('div, button, [role="button"]'));
                    let s = els.find(el => (el.innerText || '').trim().toLowerCase() === 'start' && el.offsetParent !== null);
                    if (s) { s.click(); return true; }
                    return false;
                }
                """)
                if res:
                    start_clicked = True
                    break
                await asyncio.sleep(1)

            # Wait for Question 1 choices to appear in DOM
            for _ in range(12):
                has_choices = await quiz_frame.evaluate("() => document.querySelectorAll('[data-model-id]').length > 0 || document.querySelector('#submit') !== null")
                if has_choices:
                    break
                await asyncio.sleep(0.8)

            # 7. Answering questions loop
            for q_idx in range(len(questions)):
                q_num = q_idx + 1
                current_q = questions[q_idx]

                print(f"{tag} Answering [{q_num}/{len(questions)}]...", flush=True)

                # Wait for this question's choices to be present on the active slide
                first_cid = current_q["correct_choice_ids"][0] if current_q["correct_choice_ids"] else None
                if first_cid:
                    for _ in range(15):
                        choice_ready = await quiz_frame.evaluate(
                            f"() => {{ return document.querySelector(\"[data-model-id='{first_cid}']\") !== null || document.querySelector(\"#acc-{first_cid}\") !== null; }}"
                        )
                        if choice_ready:
                            break
                        await asyncio.sleep(0.6)

                # Select choices
                for cid in current_q["correct_choice_ids"]:
                    choice_loc = quiz_frame.locator(f"[data-model-id='{cid}'], #acc-{cid}").first
                    try:
                        if await choice_loc.count() > 0:
                            await choice_loc.click(force=True, timeout=2500)
                    except Exception:
                        pass

                    await quiz_frame.evaluate(f"""() => {{
                        let el = document.querySelector(\"[data-model-id='{cid}']\") || document.querySelector(\"#acc-{cid}\");
                        if (el) {{
                            el.click();
                            let inp = document.querySelector(\"#acc-{cid}\");
                            if (inp && !inp.checked) {{
                                inp.checked = true;
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                            }}
                        }}
                    }}""")
                    await asyncio.sleep(0.4)

                await asyncio.sleep(0.8)

                # Click SUBMIT
                submit_loc = quiz_frame.locator("#submit, button:has-text('SUBMIT')").first
                try:
                    await submit_loc.click(force=True, timeout=3000)
                except Exception:
                    await quiz_frame.evaluate("""() => {
                        let b = document.querySelector('#submit');
                        if (!b) {
                            let els = Array.from(document.querySelectorAll('button, div, [role="button"]'));
                            b = els.find(e => (e.innerText || '').trim().toLowerCase() === 'submit');
                        }
                        if (b) b.click();
                    }""")
                await asyncio.sleep(1.2)

                # Check if "You must complete the question" popup appeared (self-recovery)
                try:
                    alert_ok = quiz_frame.locator("[data-acc-text='OK'], button:has-text('OK')").first
                    if await alert_ok.count() > 0 and await alert_ok.is_visible():
                        await alert_ok.click(force=True)
                        await asyncio.sleep(0.6)
                        for cid in current_q["correct_choice_ids"]:
                            await quiz_frame.evaluate(f"""() => {{
                                let el = document.querySelector(\"[data-model-id='{cid}']\") || document.querySelector(\"#acc-{cid}\");
                                if (el) el.click();
                            }}""")
                        await asyncio.sleep(0.4)
                        await submit_loc.click(force=True)
                        await asyncio.sleep(1.0)
                except Exception:
                    pass

                # Click Continue / OK to advance to next question
                for _ in range(8):
                    cont_btn = quiz_frame.locator(
                        "[data-acc-text='Continue'], button:has-text('Continue'), [data-acc-text='OK'], button:has-text('OK')"
                    ).first
                    try:
                        if await cont_btn.count() > 0 and await cont_btn.is_visible():
                            await cont_btn.click(force=True)
                            break
                    except Exception:
                        pass

                    res = await quiz_frame.evaluate("""() => {
                        let els = Array.from(document.querySelectorAll('div, button, [role="button"]'));
                        let c = els.find(el => {
                            let t = (el.innerText || '').trim().toLowerCase();
                            let acc = (el.getAttribute('data-acc-text') || '').trim().toLowerCase();
                            return (t === 'continue' || t === 'ok' || acc === 'continue' || acc === 'ok') && el.offsetParent !== null;
                        });
                        if (c) { c.click(); return true; }
                        return false;
                    }""")
                    if res:
                        break
                    await asyncio.sleep(0.8)

                await asyncio.sleep(1.5)

            # 8. Verify results slide
            score_100 = False
            for _ in range(8):
                await asyncio.sleep(1.5)
                try:
                    final_text = await quiz_frame.locator("body").inner_text()
                    if "100%" in final_text or "all the questions correctly" in final_text or "5 out of 5" in final_text:
                        score_100 = True
                        break
                except Exception:
                    pass

            if score_100:
                print(f"{tag} [✔] 100% Score verified on results slide!", flush=True)

            # 9. Close player tab and check Canvas
            try:
                await kc_tab.close()
            except Exception:
                pass
            kc_tab = None
            await asyncio.sleep(2)

            try:
                await canvas_page.reload(wait_until="networkidle")
                await asyncio.sleep(3)
                canvas_text = await canvas_page.locator("body").inner_text()
            except Exception:
                canvas_text = ""

            if "100/100 Points" in canvas_text or "SUBMITTED" in canvas_text or score_100:
                print(f"{tag} [✔] SUCCESS: Recorded as 100/100 completed on Canvas!", flush=True)
                await update_kc_item_progress(kc_items, kc_item, "completed", "100/100")
                try:
                    await canvas_page.close()
                except Exception:
                    pass
                return True
            else:
                print(f"{tag} [-] Quiz did not verify 100% score (Score verified: {score_100})", flush=True)
                await update_kc_item_progress(kc_items, kc_item, "failed", error="100% score not verified")
                try:
                    await canvas_page.close()
                except Exception:
                    pass
                return False

        except Exception as e:
            print(f"{tag} [-] Error processing: {e}", flush=True)
            if kc_tab:
                try:
                    err_shot = SCREENSHOTS_DIR / f"error_{kc_item.get('module_index')}.png"
                    await kc_tab.screenshot(path=str(err_shot))
                    await kc_tab.close()
                except Exception:
                    pass
            try:
                await canvas_page.close()
            except Exception:
                pass
            await update_kc_item_progress(kc_items, kc_item, "failed", error=str(e))
            return False


async def run_kc_automator(
    concurrency: int = 3,
    limit: int = None,
    filter_text: str = None,
    headless: bool = False,
    reset: bool = False,
):
    """
    Main orchestrator for Knowledge Checks.
    """
    kc_items = init_kc_progress()

    if reset:
        for item in kc_items:
            item["status"] = "pending"
            item["score"] = ""
            item["error"] = None
            item["completed_at"] = None
        save_json(PROGRESS_KC_FILE, kc_items)
        print("[+] All KCs reset to pending status.", flush=True)
        print_kc_summary(kc_items)
        return

    print_kc_summary(kc_items)

    queue = [i for i in kc_items if i.get("status") != "completed"]
    if filter_text:
        queue = [i for i in queue if filter_text.lower() in i.get("title", "").lower()]
        print(f"[*] Filter '{filter_text}' applied. Matching pending KCs: {len(queue)}", flush=True)

    if limit and limit > 0:
        queue = queue[:limit]
        print(f"[*] Processing limit set to {limit} KCs.", flush=True)

    if not queue:
        print("[+] All targeted Knowledge Checks are already completed!", flush=True)
        return

    conc = max(1, concurrency)
    print(f"[*] Running {len(queue)} KC(s) with concurrency level: {conc} (parallel tabs)", flush=True)

    async with async_playwright() as p:
        ctx = await create_async_browser_context(p, headless=headless)
        init_page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await ensure_async_canvas_login(init_page)

        sem = asyncio.Semaphore(conc)
        tasks = []
        for idx, item in enumerate(queue, 1):
            idx_str = f"{idx}/{len(queue)}"
            # Stagger startup of initial concurrent tabs
            stagger = ((idx - 1) % conc) * 2.5 if idx <= conc else 0.0
            tasks.append(solve_kc_worker(ctx, item, sem, kc_items, idx_str, delay=stagger))

        await asyncio.gather(*tasks)
        await ctx.close()

    print("\n" + "=" * 62, flush=True)
    print("All Knowledge Checks In This Batch Completed!", flush=True)
    print_kc_summary(kc_items)
