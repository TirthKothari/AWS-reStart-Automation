# AWS re/Start Course Automation Suite

An enterprise-grade, high-concurrency automation suite for the **AWS re/Start** curriculum on Canvas LMS (`https://awsrestart.instructure.com/courses/4639`).

Automates all three core components of the course with live browser visibility and persistent state tracking:
1. **Knowledge Checks (Quizzes)**: 100% verified score submissions via Articulate Storyline 360 client-side extraction.
2. **Hands-on Labs (AWS / Vocareum)**: High-concurrency parallel lab runner (up to 10+ concurrent tabs) with automatic URL rewriting, boot monitoring, server verification, and session termination.
3. **Study Materials**: Automated viewing and completion of course readings, guides, and external tools satisfying Canvas progression requirements.

---

## Current Course Progress

```
====================================================================
          AWS re/Start Course Automation Master Dashboard
====================================================================
 Category             Completed / Total       Progress   Status
--------------------------------------------------------------------
 Knowledge Checks       90 /   90              100.0%    COMPLETED
 Labs                   60 /  102               58.8%    IN PROGRESS
 Study Materials         3 /  194                1.5%    IN PROGRESS
--------------------------------------------------------------------
 OVERALL COURSE        153 /  386               39.6%    IN PROGRESS
====================================================================
```

---

## Architecture & Codebase Structure

```
aws_automation/
│
├── .env                              # Canvas credentials (username, password)
├── aws_automator.py                  # Master Unified CLI entry point
│
├── kc_automator.py                   # Dedicated Knowledge Checks wrapper
├── lab_automator.py                  # Dedicated Labs wrapper
├── material_automator.py             # Dedicated Study Materials wrapper
├── README.md                         # Documentation & usage manual
│
├── core/                             # Modular core package
│   ├── __init__.py                   # Package exports
│   ├── config.py                     # Centralized paths, URLs & robust .env loader
│   ├── auth.py                       # Playwright browser manager & Canvas login
│   ├── progress.py                   # Thread-safe JSON state managers & ASCII dashboards
│   ├── scanner.py                    # Canvas course module scanner & task extractor
│   ├── kc_engine.py                  # Storyline 360 client-side quiz solving engine
│   ├── lab_engine.py                 # Multi-tab Vocareum lab manager & URL rewriting
│   └── material_engine.py            # Fast concurrent study material view engine
│
├── browser_profile/                  # Persistent Chromium user profile & session cookies
├── kc_screenshots/                   # Automatic screenshots on quiz checkpoints
├── kc_progress.json                  # State tracking for 90 Knowledge Checks
├── course_progress.json              # State tracking for 102 Hands-on Labs
├── material_progress.json            # State tracking for 194 Study Materials
└── extracted_tasks.json              # Master catalog of all 391 course items
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher
- Chromium browser managed via Playwright

### 2. Install Dependencies
```powershell
pip install playwright beautifulsoup4 python-dotenv
playwright install chromium
```

### 3. Configure Credentials
Create a `.env` file in the project root:
```env
username=your_canvas_email@example.com
password=your_canvas_password
```
*(Supports both UTF-8 and UTF-16 encodings automatically).*

---

## Quick Start & Usage

### 1. View Master Dashboard
Check overall progress and category breakdown at any time without opening the browser:
```powershell
python aws_automator.py --status
```
Or simply:
```powershell
python aws_automator.py status
```

---

### 2. Automating Knowledge Checks (Quizzes)

The Knowledge Check automator uses **Way 1 client-side reverse-engineering**:
- Extracts questions and 100% correct answer IDs directly from `html5/data/js/data.js` in browser memory.
- Injects anti-throttling scripts into background tabs so Storyline slide timelines never freeze.
- Supports launch staggering to avoid LTI session collisions.
- Automatically handles resume dialogs and self-recovers if a click is missed.

```powershell
# Run next 6 pending Knowledge Checks with 3 concurrent tabs (headed mode)
python aws_automator.py kc --concurrency 3 --limit 6

# Run with 2 concurrent tabs
python aws_automator.py kc --concurrency 2 --limit 4

# Target specific topics using a title filter
python aws_automator.py kc --filter "EC2"
python aws_automator.py kc --filter "VPC"

# Run headless (in background)
python aws_automator.py kc --headless --concurrency 3 --limit 5

# Check KC status only
python aws_automator.py kc --status
```

*Note: You can also use the dedicated wrapper:*
```powershell
python kc_automator.py --concurrency 3 --limit 6
```

---

### 3. Automating Hands-on Labs

The Lab automator manages a **parallel multi-tab pool** (up to 10+ tabs simultaneously):
- Launches labs concurrently and automatically rewrites Vocareum URLs from `m=editor` to `m=clabide`.
- Monitors the `#vmstatus` LED indicator until it turns green (`led-green` / ready).
- Clicks `Submit` and polls the Vocareum backend to verify submission confirmation.
- Clicks `End Lab`, confirms the modal, closes the tab, and immediately launches the next lab from the queue.

```powershell
# Run 10 labs concurrently (default concurrency: 10)
python aws_automator.py labs --concurrency 10 --limit 10

# Run 5 labs with a topic filter
python aws_automator.py labs --concurrency 5 --filter "S3"

# Check Labs status only
python aws_automator.py labs --status
```

*Note: You can also use the dedicated wrapper:*
```powershell
python lab_automator.py --concurrency 10 --limit 10
```

---

### 4. Automating Study Materials

The Study Material automator rapidly visits course readings, guides, and external links:
- Satisfies Canvas `must_view_requirement` by loading items with authenticated session cookies.
- Automatically clicks `Mark as done` if required by the page.
- Handles external tool launches and popups.
- Runs at high concurrency (default 5 tabs).

```powershell
# View next 20 study materials with 5 parallel tabs
python aws_automator.py materials --concurrency 5 --limit 20

# Run all remaining pending study materials
python aws_automator.py materials --concurrency 5

# Check Study Materials status only
python aws_automator.py materials --status
```

*Note: You can also use the dedicated wrapper:*
```powershell
python material_automator.py --concurrency 5 --limit 20
```

---

### 5. Complete Course Automation Sequence

To run all remaining tasks across all three categories in coordinated stages:
```powershell
python aws_automator.py all
```
*Executes Study Materials first, followed by Knowledge Checks, and finally Hands-on Labs.*

---

### 6. Refreshing Course Structure

If new modules or assignments are published on Canvas, rescan the entire course:
```powershell
python aws_automator.py scan --refresh
```

---

## Command Reference Summary

| Parameter | Options / Type | Description |
|---|---|---|
| `mode` | `kc`, `labs`, `materials`, `status`, `scan`, `all` | Selects which component of the course to automate |
| `--concurrency` | Integer (e.g. `2`, `3`, `5`, `10`) | Number of tabs running in parallel |
| `--limit` | Integer (e.g. `5`, `10`, `20`) | Caps the total number of items to process in the run |
| `--filter` | String (e.g. `"EC2"`, `"Linux"`) | Case-insensitive title substring filter |
| `--headless` | Flag | Runs Chromium invisibly in the background |
| `--status` | Flag | Displays the status dashboard for the selected mode and exits |
| `--reset` | Flag | Resets items of the selected mode back to `pending` |
| `--refresh` | Flag | Forces re-extraction of the Canvas modules tree |

---

## Technical Details & Robustness

### Articulate Storyline 360 Client-Side Evaluation
- SCORM packages rendered via ContentController evaluate scores locally before sending LMS commits.
- Quizzes dynamically fetch `html5/data/js/data.js` containing scenes, slides, questions, and interactions.
- Inside `interactions[i].answers`, elements with `status == "correct"` identify exact choice IDs (`statement.choiceid`).
- Matching DOM elements (`[data-model-id='<id>']`) are selected and verified prior to submitting.

### Multi-Tab Concurrency & Anti-Throttling
- Chromium throttles background tabs by default (`document.hidden = true`), which causes Storyline 360 animation timelines to freeze mid-transition.
- The engine injects property overrides (`Object.defineProperty(document, 'hidden', { get: () => false })`) into both outer tabs and inner SCORM iframes.
- Initial tab launches are staggered by 2.5 seconds to eliminate Canvas LTI token request contention.
- Self-healing recovery automatically detects and dismisses *"You must complete the question before submitting"* popups, re-selects choices via DOM evaluation, and resubmits.

### Vocareum Lab Lifecycle Management
- Labs redirecting to the legacy editor (`m=editor`) frequently stall or timeout. The engine rewrites navigation URLs to `m=clabide` immediately upon launch.
- Non-blocking polling monitors `#vmstatus` (`led-green`) across all active tabs in parallel.
- Submissions are validated against the Vocareum backend (`submit_in_progress` and `.gritter-item`) before issuing the final `#endclabsbtn` teardown.
