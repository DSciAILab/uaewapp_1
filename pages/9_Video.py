# ==============================================================================
# VIDEO SHOOTING - PAGE
# ==============================================================================
from task_app import render_task_page

PAGE_TITLE = "Video Shooting"
FIXED_TASK = "Video Shooting"
TASK_ALIASES = [
    r"\bvideo\s*shoot(?:ing)?\b",
    r"\bfilming\b",
    r"\bmedia\s*shoot\b",
]

render_task_page(page_title=PAGE_TITLE, fixed_task=FIXED_TASK, task_aliases=TASK_ALIASES)
