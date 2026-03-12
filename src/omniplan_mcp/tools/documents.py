import json
from omniplan_mcp.app import mcp
from omniplan_mcp.jxa import run_omnijs


@mcp.tool()
async def list_documents() -> str:
    """List all currently open OmniPlan documents.
    Use the returned document names as the document_name parameter in other tools.
    """
    script = """
const docs = [];
for (const doc of document.projects || []) {
  // top-level: enumerate via app
}
// Access via app windows
const app = Application('OmniPlan 4');
const result = [];
for (const doc of app.documents()) {
  result.push({ name: doc.name(), path: doc.path() || null });
}
return result;
"""

    # For list_documents we use JXA directly (not OmniJS bridge) since we need app-level access
    from omniplan_mcp.jxa import run_jxa, _escape
    jxa_script = """
const app = Application('OmniPlan 4');
const docs = app.documents();
const result = docs.map(d => ({ name: d.name(), path: d.path() || null }));
JSON.stringify({ ok: true, data: result });
"""
    raw = await run_jxa(jxa_script)
    envelope = json.loads(raw)
    return json.dumps(envelope.get("data", []))
