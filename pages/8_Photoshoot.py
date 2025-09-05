# ==============================================================================
# PHOTOSHOOT - PAGE
# ==============================================================================
from task_app import render_task_page

# exact title in tab + page
PAGE_TITLE = "Photoshoot"
FIXED_TASK = "Photoshoot"
TASK_ALIASES = [r"\bphoto\s*shoot\b", r"\bphotoshoot\b", r"\bphoto\b"]

render_task_page(page_title=PAGE_TITLE, fixed_task=FIXED_TASK, task_aliases=TASK_ALIASES)
