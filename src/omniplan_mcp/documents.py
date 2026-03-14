import json
from omniplan_mcp.server import mcp

@mcp.tool()
async def list_documents() -> str:
    """List all currently open OmniPlan documents.
    Note: task tools now always operate on the current front document.
    """
    # Use JXA directly (not OmniJS bridge) since we need app-level access
    from omniplan_mcp.jxa import run_jxa
    jxa_script = """
const app = Application('OmniPlan');
const docs = app.documents();
const result = docs.map(d => {
  let path = null;
  try {
    const rawPath = d.path();
    path = rawPath ? String(rawPath) : null;
  } catch (_) {
    path = null;
  }
  return { name: d.name(), path };
});
JSON.stringify({ ok: true, data: result });
"""
    raw = await run_jxa(jxa_script)
    envelope = json.loads(raw)
    return json.dumps(envelope.get("data", []))
