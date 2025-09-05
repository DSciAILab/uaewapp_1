# ==============================================================================
# BLOOD TEST - PAGE
# ==============================================================================
from task_app import render_task_page

PAGE_TITLE = "Blood Test"
FIXED_TASK = "Blood Test"
TASK_ALIASES = [r"\bblood\s*test\b", r"\bblood\b"]

render_task_page(page_title=PAGE_TITLE, fixed_task=FIXED_TASK, task_aliases=TASK_ALIASES)
