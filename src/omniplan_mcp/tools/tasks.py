import json
from typing import Optional
from omniplan_mcp.app import mcp
from omniplan_mcp.jxa import run_omnijs

# Valid color names mapping to Omni Automation Color constants
VALID_COLORS = {"red", "orange", "yellow", "green", "blue", "purple", "brown", "gray", "clear"}

TASK_COLORS = {
    "red":    "Color.RGB(0.85, 0.20, 0.15, 1)",
    "orange": "Color.RGB(0.95, 0.55, 0.10, 1)",
    "yellow": "Color.RGB(0.95, 0.85, 0.10, 1)",
    "green":  "Color.RGB(0.20, 0.70, 0.25, 1)",
    "blue":   "Color.RGB(0.15, 0.45, 0.85, 1)",
    "purple": "Color.RGB(0.55, 0.20, 0.75, 1)",
    "brown":  "Color.RGB(0.55, 0.35, 0.20, 1)",
    "gray":   "Color.RGB(0.55, 0.55, 0.55, 1)",
    "clear":  "null",  # resets to default
}


def _doc_selector(document_name: Optional[str]) -> str:
    """Returns JS expression to get the target document's root project."""
    if document_name:
        return f"""
const _docs = Application('OmniPlan 4').documents();
const _doc = _docs.find(d => d.name() === {json.dumps(document_name)});
if (!_doc) throw new Error('Document not found: {document_name}');
const _proj = _doc.project();
""".strip()
    else:
        return "const _proj = Application('OmniPlan 4').documents()[0].project();"


def _task_to_obj() -> str:
    """JS helper function to serialize a Task to a plain object."""
    return """
function taskToObj(task) {
  let colorName = null;
  try {
    const style = task.style;
    if (style) {
      const c = style.valueForAttribute('gantt-bar-color') || style.valueForAttribute('gantt-fill-color');
      if (c) colorName = c.toString();
    }
  } catch(e) {}

  const effort = task.effort || 0;
  const effortDone = task.effortDone || 0;
  const completionPct = effort > 0 ? Math.round((effortDone / effort) * 100) : 0;

  return {
    id: String(task.uniqueID),
    title: task.title || '',
    note: task.note || '',
    type: String(task.taskType).replace('TaskType.', ''),
    completed: effortDone >= effort && effort > 0,
    completion_pct: completionPct,
    start_date: task.startDate ? task.startDate.toISOString() : null,
    end_date: task.endDate ? task.endDate.toISOString() : null,
    manual_start_date: task.manualStartDate ? task.manualStartDate.toISOString() : null,
    manual_end_date: task.manualEndDate ? task.manualEndDate.toISOString() : null,
    effort_seconds: effort,
    effort_done_seconds: effortDone,
    color: colorName,
    parent_id: task.parent ? String(task.parent.uniqueID) : null,
  };
}
"""


@mcp.tool()
async def query_tasks(
    keyword: Optional[str] = None,
    task_type: Optional[str] = None,
    completed: Optional[bool] = None,
    color: Optional[str] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
    document_name: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Query tasks in an OmniPlan document with optional filters.

    Args:
        keyword: Filter by title or note containing this text (case-insensitive).
        task_type: One of: task, group, milestone, hammock.
        completed: True = completed only, False = incomplete only, None = all.
        color: Filter by bar color. One of: red, orange, yellow, green, blue, purple, brown, gray, clear.
        due_before: ISO date string (e.g. 2025-12-31). Tasks ending before this date.
        due_after: ISO date string (e.g. 2025-01-01). Tasks ending after this date.
        document_name: Name of the open OmniPlan document. Uses frontmost document if omitted.
        limit: Maximum number of tasks to return (default 50).
    """
    if color and color not in VALID_COLORS:
        return json.dumps({"error": f"Invalid color. Choose from: {', '.join(sorted(VALID_COLORS))}"})

    doc_sel = _doc_selector(document_name)
    task_to_obj = _task_to_obj()

    filters = []
    if keyword:
        kw = json.dumps(keyword.lower())
        filters.append(f"(t.title || '').toLowerCase().includes({kw}) || (t.note || '').toLowerCase().includes({kw})")
    if task_type:
        filters.append(f"String(t.taskType).replace('TaskType.', '') === {json.dumps(task_type)}")
    if completed is True:
        filters.append("(t.effortDone >= t.effort && t.effort > 0)")
    elif completed is False:
        filters.append("!(t.effortDone >= t.effort && t.effort > 0)")
    if due_before:
        filters.append(f"t.endDate && t.endDate < new Date({json.dumps(due_before)})")
    if due_after:
        filters.append(f"t.endDate && t.endDate > new Date({json.dumps(due_after)})")

    filter_expr = " && ".join(filters) if filters else "true"

    script = f"""
{doc_sel}
{task_to_obj}

function flatten(task) {{
  let results = [];
  for (const child of task.subtasks()) {{
    results.push(child);
    results = results.concat(flatten(child));
  }}
  return results;
}}

const root = _proj.rootTask;
const allTasks = flatten(root);
const filtered = allTasks.filter(t => {filter_expr});
return filtered.slice(0, {limit}).map(taskToObj);
"""
    result = await run_omnijs(script)
    return json.dumps(result)


@mcp.tool()
async def get_task(
    task_id: str,
    document_name: Optional[str] = None,
) -> str:
    """Get full details of a single task by its unique ID.

    Args:
        task_id: The uniqueID of the task.
        document_name: Name of the open OmniPlan document. Uses frontmost document if omitted.
    """
    doc_sel = _doc_selector(document_name)
    task_to_obj = _task_to_obj()

    script = f"""
{doc_sel}
{task_to_obj}

function findById(task, id) {{
  if (String(task.uniqueID) === id) return task;
  for (const child of task.subtasks()) {{
    const found = findById(child, id);
    if (found) return found;
  }}
  return null;
}}

const task = findById(_proj.rootTask, {json.dumps(task_id)});
if (!task) throw new Error('Task not found: {task_id}');
return taskToObj(task);
"""
    result = await run_omnijs(script)
    return json.dumps(result)


@mcp.tool()
async def create_task(
    title: str,
    parent_id: Optional[str] = None,
    task_type: Optional[str] = None,
    note: Optional[str] = None,
    manual_start_date: Optional[str] = None,
    manual_end_date: Optional[str] = None,
    color: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """Create a new task in an OmniPlan document.

    Args:
        title: Task title.
        parent_id: uniqueID of the parent task. If omitted, adds to root.
        task_type: One of: task, group, milestone, hammock. Defaults to task.
        note: Optional task description.
        manual_start_date: ISO date string for manual start.
        manual_end_date: ISO date string for manual end.
        color: Bar color. One of: red, orange, yellow, green, blue, purple, brown, gray.
        document_name: Name of the open OmniPlan document. Uses frontmost document if omitted.
    """
    if color and color not in VALID_COLORS:
        return json.dumps({"error": f"Invalid color. Choose from: {', '.join(sorted(VALID_COLORS))}"})

    doc_sel = _doc_selector(document_name)
    task_to_obj = _task_to_obj()

    set_type = f"newTask.taskType = TaskType.{task_type};" if task_type else ""
    set_note = f"newTask.note = {json.dumps(note)};" if note else ""
    set_start = f"newTask.manualStartDate = new Date({json.dumps(manual_start_date)});" if manual_start_date else ""
    set_end = f"newTask.manualEndDate = new Date({json.dumps(manual_end_date)});" if manual_end_date else ""

    if color and color != "clear":
        color_val = TASK_COLORS[color]
        set_color = f"newTask.style.set({color_val}, {{forAttribute: 'gantt-bar-color'}});"
    elif color == "clear":
        set_color = "newTask.style.clear('gantt-bar-color');"
    else:
        set_color = ""

    script = f"""
{doc_sel}
{task_to_obj}

function findById(task, id) {{
  if (String(task.uniqueID) === id) return task;
  for (const child of task.subtasks()) {{
    const found = findById(child, id);
    if (found) return found;
  }}
  return null;
}}

const parentId = {json.dumps(parent_id)};
const parent = parentId ? findById(_proj.rootTask, parentId) : _proj.rootTask;
if (!parent) throw new Error('Parent task not found: ' + parentId);

const newTask = parent.addSubtask();
newTask.title = {json.dumps(title)};
{set_type}
{set_note}
{set_start}
{set_end}
{set_color}

return taskToObj(newTask);
"""
    result = await run_omnijs(script)
    return json.dumps(result)


@mcp.tool()
async def update_task(
    task_id: str,
    title: Optional[str] = None,
    note: Optional[str] = None,
    completed: Optional[bool] = None,
    manual_start_date: Optional[str] = None,
    manual_end_date: Optional[str] = None,
    color: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """Update an existing task. Only provided fields are changed.

    Args:
        task_id: The uniqueID of the task.
        title: New title.
        note: New note text.
        completed: True to mark complete, False to mark incomplete.
        manual_start_date: ISO date string, or empty string to clear.
        manual_end_date: ISO date string, or empty string to clear.
        color: Bar color. One of: red, orange, yellow, green, blue, purple, brown, gray, clear.
        document_name: Name of the open OmniPlan document. Uses frontmost document if omitted.
    """
    if color and color not in VALID_COLORS:
        return json.dumps({"error": f"Invalid color. Choose from: {', '.join(sorted(VALID_COLORS))}"})

    doc_sel = _doc_selector(document_name)
    task_to_obj = _task_to_obj()

    updates = []
    if title is not None:
        updates.append(f"task.title = {json.dumps(title)};")
    if note is not None:
        updates.append(f"task.note = {json.dumps(note)};")
    if completed is True:
        updates.append("if (task.effort > 0) { task.effortDone = task.effort; }")
    elif completed is False:
        updates.append("task.effortDone = 0;")
    if manual_start_date == "":
        updates.append("task.manualStartDate = null;")
    elif manual_start_date is not None:
        updates.append(f"task.manualStartDate = new Date({json.dumps(manual_start_date)});")
    if manual_end_date == "":
        updates.append("task.manualEndDate = null;")
    elif manual_end_date is not None:
        updates.append(f"task.manualEndDate = new Date({json.dumps(manual_end_date)});")
    if color == "clear":
        updates.append("task.style.clear('gantt-bar-color');")
    elif color is not None:
        color_val = TASK_COLORS[color]
        updates.append(f"task.style.set({color_val}, {{forAttribute: 'gantt-bar-color'}});")

    if not updates:
        return json.dumps({"error": "No fields to update."})

    update_block = "\n".join(updates)

    script = f"""
{doc_sel}
{task_to_obj}

function findById(task, id) {{
  if (String(task.uniqueID) === id) return task;
  for (const child of task.subtasks()) {{
    const found = findById(child, id);
    if (found) return found;
  }}
  return null;
}}

const task = findById(_proj.rootTask, {json.dumps(task_id)});
if (!task) throw new Error('Task not found: {task_id}');

{update_block}

return taskToObj(task);
"""
    result = await run_omnijs(script)
    return json.dumps(result)


@mcp.tool()
async def delete_task(
    task_id: str,
    document_name: Optional[str] = None,
) -> str:
    """Delete a task by its unique ID.

    Args:
        task_id: The uniqueID of the task to delete.
        document_name: Name of the open OmniPlan document. Uses frontmost document if omitted.
    """
    doc_sel = _doc_selector(document_name)

    script = f"""
{doc_sel}

function findById(task, id) {{
  if (String(task.uniqueID) === id) return task;
  for (const child of task.subtasks()) {{
    const found = findById(child, id);
    if (found) return found;
  }}
  return null;
}}

const task = findById(_proj.rootTask, {json.dumps(task_id)});
if (!task) throw new Error('Task not found: {task_id}');
const title = task.title;
task.remove();
return {{ deleted: true, id: {json.dumps(task_id)}, title: title }};
"""
    result = await run_omnijs(script)
    return json.dumps(result)
