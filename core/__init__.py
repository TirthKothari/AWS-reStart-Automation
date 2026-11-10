"""
AWS re/Start Automation Core Package.
Provides centralized modules for configuration, authentication, progress tracking,
scanning, and specialized automation engines for Knowledge Checks, Labs, and Study Materials.
"""

from .config import (
    WORKSPACE_DIR,
    PROFILE_DIR,
    SCREENSHOTS_DIR,
    KC_REPO_DIR,
    PROGRESS_KC_FILE,
    PROGRESS_LABS_FILE,
    TASKS_FILE,
    COURSE_URL,
    LOGIN_URL,
    MODULES_URL,
    load_credentials,
)

__all__ = [
    "WORKSPACE_DIR",
    "PROFILE_DIR",
    "SCREENSHOTS_DIR",
    "KC_REPO_DIR",
    "PROGRESS_KC_FILE",
    "PROGRESS_LABS_FILE",
    "TASKS_FILE",
    "COURSE_URL",
    "LOGIN_URL",
    "MODULES_URL",
    "load_credentials",
]
