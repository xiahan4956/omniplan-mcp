import json
from omniplan_mcp.app import mcp

@mcp.tool()
async def list_documents() -> str:
    """List all currently open OmniPlan documents.
    Use the returned document names as the document_name parameter in other tools.
    """
    # Use JXA directly (not OmniJS bridge) since we need app-level access
    from omniplan_mcp.jxa import run_jxa
    jxa_script = """
const app = Application('OmniPlan 4');
const docs = app.documents();
const result = docs.map(d => ({ name: d.name(), path: d.path() || null }));
JSON.stringify({ ok: true, data: result });
"""
    raw = await run_jxa(jxa_script)
    envelope = json.loads(raw)
    return json.dumps(envelope.get("data", []))
