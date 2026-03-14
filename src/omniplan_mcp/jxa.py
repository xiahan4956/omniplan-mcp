import asyncio
import json
from typing import Any

DEFAULT_TIMEOUT = 30.0
_LOCK = asyncio.Lock()


def _escape(value: str) -> str:
    return json.dumps(value)


def _friendly_error(stderr: str) -> str:
    low = stderr.lower()
    if "not running" in low and "omniplan" in low:
        return "OmniPlan is not running. Please open OmniPlan and try again."
    if any(k in low for k in ("not authorized", "not permitted", "apple events", "(-1743)")):
        return (
            "macOS blocked Automation access to OmniPlan. "
            "Grant permission in System Settings > Privacy & Security > Automation."
        )
    return f"JXA error: {stderr.strip()}"


async def run_jxa(script: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    async with _LOCK:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-l", "JavaScript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as e:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"JXA timed out after {timeout:.0f}s.") from e

        if proc.returncode != 0:
            raise RuntimeError(_friendly_error(err.decode("utf-8", errors="replace")))

        return out.decode("utf-8", errors="replace").strip()


async def run_omnijs(script: str, timeout: float = DEFAULT_TIMEOUT) -> Any:
    """Run JavaScript inside OmniPlan via evaluateJavascript bridge."""
    wrapped = f"""
(function() {{
  try {{
    const __data = (function() {{
{script}
    }})();
    return JSON.stringify({{ ok: true, data: __data }});
  }} catch(e) {{
    return JSON.stringify({{ ok: false, error: e && e.message ? e.message : String(e) }});
  }}
}})()
""".strip()

    outer = f"""
const app = Application('OmniPlan');
const result = app.evaluateJavascript({_escape(wrapped)});
result;
""".strip()

    raw = await run_jxa(outer, timeout=timeout)

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError("OmniPlan returned malformed JSON.") from e

    if not isinstance(envelope, dict) or envelope.get("ok") is not True:
        error = envelope.get("error", "Unknown OmniPlan error.")
        raise RuntimeError(str(error))

    return envelope.get("data")
