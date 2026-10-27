"""Local KaTeX AST verification oracle using host node/katex runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class KaTeXParseError:
    """Represents a KaTeX parser exception with context."""

    math_content: str
    display_mode: bool
    error_message: str


def _get_node_env() -> dict[str, str]:
    """Build environment variables ensuring NODE_PATH includes standard KaTeX locations."""
    env = os.environ.copy()
    candidate_paths = [
        "/home/jh/.npm-global/lib/node_modules",
        "/home/linuxbrew/.linuxbrew/lib/node_modules",
        "/usr/lib/node_modules",
        "/usr/local/lib/node_modules",
        os.path.expanduser("~/.npm-global/lib/node_modules"),
    ]
    current_node_path = env.get("NODE_PATH", "")
    if current_node_path:
        candidate_paths.insert(0, current_node_path)
    env["NODE_PATH"] = ":".join(p for p in candidate_paths if p)
    return env


def is_katex_available() -> bool:
    """Check if node and the katex package are available in the execution environment."""
    node_bin = shutil.which("node")
    if not node_bin:
        return False
    check_script = "try { require('katex'); process.exit(0); } catch (e) { process.exit(1); }"
    try:
        res = subprocess.run(
            [node_bin, "-e", check_script],
            capture_output=True,
            timeout=5,
            env=_get_node_env(),
            check=False,
        )
        return res.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def run_local_katex_verification(math_blocks: list[tuple[str, bool]]) -> list[KaTeXParseError]:
    """Validate a list of (math_content, is_display) tuples against KaTeX.

    Returns a list of parse errors encountered. Returns empty list if KaTeX is unavailable.
    """
    if not math_blocks:
        return []

    node_bin = shutil.which("node")
    if not node_bin:
        return []

    js_worker = """
    const readline = require('readline');
    let katex;
    try {
        katex = require('katex');
    } catch (e) {
        process.stdout.write(JSON.stringify({ unavailable: true }));
        process.exit(0);
    }
    const rl = readline.createInterface({ input: process.stdin });

    let inputData = '';
    rl.on('line', (line) => { inputData += line; });
    rl.on('close', () => {
        let blocks = [];
        try {
            blocks = JSON.parse(inputData);
        } catch (e) {
            process.stdout.write(JSON.stringify([]));
            process.exit(0);
        }
        const errors = [];
        for (const item of blocks) {
            try {
                katex.renderToString(item.math, {
                    displayMode: item.display,
                    throwOnError: true
                });
            } catch (err) {
                errors.push({
                    math: item.math,
                    display: item.display,
                    error: err.message
                });
            }
        }
        process.stdout.write(JSON.stringify(errors));
    });
    """

    payload = [{"math": m, "display": d} for m, d in math_blocks]
    try:
        proc = subprocess.run(
            [node_bin, "-e", js_worker],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=15,
            env=_get_node_env(),
        )
        raw_output = proc.stdout.decode("utf-8").strip()
        if not raw_output:
            return []
        data = json.loads(raw_output)
        if isinstance(data, dict) and data.get("unavailable"):
            return []
        if isinstance(data, list):
            return [
                KaTeXParseError(
                    math_content=str(e.get("math", "")),
                    display_mode=bool(e.get("display", False)),
                    error_message=str(e.get("error", "Unknown KaTeX parse error")),
                )
                for e in data
            ]
        return []
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return []
