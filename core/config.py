"""
Central Configuration and Environment Loader for AWS re/Start Course Automation.
Safely extracts credentials from .env and exposes standardized directory paths and URLs.
"""

import os
import sys
from pathlib import Path
from dotenv import dotenv_values

# Enable real-time line buffering on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# File and Directory Paths
WORKSPACE_DIR = Path(__file__).parent.parent.resolve()
PROFILE_DIR = (WORKSPACE_DIR / "browser_profile").resolve()
SCREENSHOTS_DIR = (WORKSPACE_DIR / "kc_screenshots").resolve()
KC_REPO_DIR = (WORKSPACE_DIR / "kc_repo" / "KC").resolve()

# State & Progress Files
PROGRESS_KC_FILE = (WORKSPACE_DIR / "kc_progress.json").resolve()
PROGRESS_LABS_FILE = (WORKSPACE_DIR / "course_progress.json").resolve()
TASKS_FILE = (WORKSPACE_DIR / "extracted_tasks.json").resolve()
PROGRESS_MATERIALS_FILE = (WORKSPACE_DIR / "material_progress.json").resolve()

# Canvas URLs
BASE_CANVAS_URL = "https://awsrestart.instructure.com"
COURSE_ID = "4639"
COURSE_URL = f"{BASE_CANVAS_URL}/courses/{COURSE_ID}"
LOGIN_URL = f"{BASE_CANVAS_URL}/login/canvas"
MODULES_URL = f"{COURSE_URL}/modules"


def load_credentials():
    """
    Loads username and password credentials safely from .env file.
    Supports both UTF-8 and UTF-16 encodings (common on Windows PowerShell).
    """
    env_path = WORKSPACE_DIR / ".env"
    if not env_path.exists():
        raise FileNotFoundError(
            f"Credentials file '{env_path}' not found! "
            "Please create a .env file with 'username' and 'password'."
        )

    config = {}
    # Try UTF-8 first
    try:
        config = dotenv_values(str(env_path), encoding="utf-8")
    except Exception:
        pass

    # If missing or failed, try UTF-16
    if not config or not config.get("username"):
        try:
            config = dotenv_values(str(env_path), encoding="utf-16")
        except Exception:
            pass

    username = config.get("username")
    password = config.get("password")

    if not username or not password:
        raise ValueError(
            "Both 'username' and 'password' must be defined in the .env file."
        )

    return username.strip(), password.strip()


def ensure_directories():
    """Ensures required runtime directories exist."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
