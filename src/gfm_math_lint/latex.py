"""Zero-dependency LaTeX structural validator and optional local KaTeX strict runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

_VALID_SINGLE_DELIMITERS: frozenset[str] = frozenset({".", "(", ")", "[", "]", "|", "/", "<", ">"})
_VALID_ESCAPED_DELIMITERS: frozenset[str] = frozenset({"{", "}", "|"})
_VALID_NAMED_DELIMITERS: frozenset[str] = frozenset(
    {
        "lvert",
        "rvert",
        "lVert",
        "rVert",
        "lbrace",
        "rbrace",
        "langle",
        "rangle",
        "lfloor",
        "rfloor",
        "lceil",
        "rceil",
        "vert",
        "Vert",
        "backslash",
        "uparrow",
        "downarrow",
        "updownarrow",
        "Uparrow",
        "Downarrow",
        "Updownarrow",
        "ulcorner",
        "urcorner",
        "llcorner",
        "lrcorner",
        "lgroup",
        "rgroup",
        "lmoustache",
        "rmoustache",
        "lbrack",
        "rbrack",
        "lt",
        "gt",
        "llbracket",
        "rrbracket",
        "lang",
        "rang",
        "lBrace",
        "rBrace",
    }
)
_TEXT_MODE_COMMANDS: frozenset[str] = frozenset({"text", "textrm", "textit", "textbf", "texttt", "textsf"})
_FRAC_COMMANDS: frozenset[str] = frozenset({"frac", "dfrac", "tfrac", "cfrac"})


@dataclass(frozen=True)
class LaTeXIssue:
    """Structural or syntax issue detected by the pure-Python LaTeX validator."""

    category: str
    message: str
    math_content: str
    display_mode: bool = False
    offset: int = 0


@dataclass(frozen=True)
class KaTeXDiagnostic:
    """Diagnostic returned by the optional local Node.js KaTeX strict runner."""

    math_content: str
    display_mode: bool
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class _TextModeFrame:
    brace_depth: int
    in_math: bool = False


def _skip_ws_and_comments(tex: str, pos: int) -> int:
    n = len(tex)
    while pos < n:
        if tex[pos].isspace():
            pos += 1
        elif tex[pos] == "%":
            nl = tex.find("\n", pos)
            if nl == -1:
                return n
            pos = nl + 1
        else:
            break
    return pos


def _read_braced_name(tex: str, pos: int) -> tuple[str | None, int]:
    """Read a `{name}` argument starting after optional whitespace/comments, or return (None, pos)."""
    p = _skip_ws_and_comments(tex, pos)
    n = len(tex)
    if p >= n or tex[p] != "{":
        return None, pos
    end = tex.find("}", p + 1)
    if end == -1:
        return None, pos
    return tex[p + 1 : end].strip(), end + 1


def _consume_delimiter(tex: str, pos: int) -> tuple[bool, int]:
    """Check and consume a valid \\left / \\right delimiter token starting at `pos`."""
    p = _skip_ws_and_comments(tex, pos)
    n = len(tex)
    if p >= n:
        return False, pos
    ch = tex[p]
    if ch in _VALID_SINGLE_DELIMITERS:
        return True, p + 1
    if ch == "\\":
        if p + 1 >= n:
            return False, pos
        nxt = tex[p + 1]
        if nxt in _VALID_ESCAPED_DELIMITERS:
            return True, p + 2
        if nxt.isalpha():
            j = p + 1
            while j < n and tex[j].isalpha():
                j += 1
            cmd = tex[p + 1 : j]
            if cmd in _VALID_NAMED_DELIMITERS:
                return True, j
        return False, pos
    return False, pos


def _consume_single_arg(tex: str, pos: int) -> tuple[bool, int]:
    """Consume one TeX macro argument (braced group, control sequence, or single token)."""
    p = _skip_ws_and_comments(tex, pos)
    n = len(tex)
    if p >= n or tex[p] == "}":
        return False, pos
    if tex[p] == "{":
        depth = 1
        j = p + 1
        while j < n and depth > 0:
            if tex[j] == "\\":
                j += 2
                continue
            if tex[j] == "%":
                nl = tex.find("\n", j)
                if nl == -1:
                    return False, pos
                j = nl + 1
                continue
            if tex[j] == "{":
                depth += 1
            elif tex[j] == "}":
                depth -= 1
            j += 1
        if depth != 0:
            return False, pos
        return True, j
    if tex[p] == "\\":
        if p + 1 >= n:
            return False, pos
        if tex[p + 1].isalpha():
            j = p + 1
            while j < n and tex[j].isalpha():
                j += 1
            return True, j
        return True, p + 2
    return True, p + 1


def _skip_script_arg_end(tex: str, pos: int) -> int | None:
    """Return the index immediately after a subscript/superscript argument, or None if dangling."""
    p = _skip_ws_and_comments(tex, pos)
    n = len(tex)
    if p >= n or tex[p] in ("}", "&"):
        return None
    if tex.startswith("\\\\", p):
        return None
    ok, end_pos = _consume_single_arg(tex, p)
    return end_pos if ok else None


def validate_latex(tex: str, display: bool = False) -> list[LaTeXIssue]:
    """Validate LaTeX math content for structural balance and common syntax errors.

    Pure-Python zero-dependency validator checking:
    - Balanced `{` and `}` braces (respecting `\\\\` linebreaks, `\\{`/`\\}` escapes, and `%` comments)
    - Matched `\\begin{env}` / `\\end{env}` pairs
    - Matched `\\left` / `\\right` delimiters with valid delimiter tokens
    - Unescaped `_` inside text-mode macros (`\\text{...}`, etc.)
    - Missing arguments to `\\frac`-family commands
    - Dangling or doubled `_` / `^` scripts
    """
    issues: list[LaTeXIssue] = []
    n = len(tex)
    i = 0

    brace_stack: list[int] = []
    env_stack: list[tuple[str, int]] = []
    left_stack: list[int] = []
    text_mode_stack: list[_TextModeFrame] = []
    # Tracks per-brace-depth script operators seen on the current atom, and arg end offset
    atom_scripts: dict[int, set[str]] = {}
    script_arg_until: dict[int, int] = {}

    while i < n:
        ch = tex[i]
        depth = len(brace_stack)
        in_text_mode = bool(text_mode_stack) and not text_mode_stack[-1].in_math

        if ch.isspace():
            i += 1
            continue

        # 2. TeX comment '%'
        if ch == "%":
            nl = tex.find("\n", i)
            if nl == -1:
                break
            i = nl + 1
            continue

        # Clear atom script state at `depth` when a non-script token arrives after the script arg
        if ch not in ("_", "^") and i >= script_arg_until.get(depth, -1):
            atom_scripts.pop(depth, None)
            script_arg_until.pop(depth, None)

        # 1. Backslash sequences
        if ch == "\\":
            if i + 1 < n and tex[i + 1] == "\\":
                # Double backslash '\\' is a linebreak token, NOT an escape of the next char
                i += 2
                continue
            if i + 1 < n and tex[i + 1].isalpha():
                j = i + 1
                while j < n and tex[j].isalpha():
                    j += 1
                cmd = tex[i + 1 : j]
                if cmd == "begin":
                    env_name, next_pos = _read_braced_name(tex, j)
                    if env_name is not None:
                        env_stack.append((env_name, i))
                        i = next_pos
                        continue
                elif cmd == "end":
                    env_name, next_pos = _read_braced_name(tex, j)
                    if env_name is not None:
                        if not env_stack:
                            issues.append(
                                LaTeXIssue(
                                    category="unmatched-environment",
                                    message=(
                                        f"Unexpected '\\end{{{env_name}}}' without matching '\\begin{{{env_name}}}'."
                                    ),
                                    math_content=tex,
                                    display_mode=display,
                                    offset=i,
                                )
                            )
                        elif env_stack[-1][0] != env_name:
                            opened_name, _ = env_stack.pop()
                            issues.append(
                                LaTeXIssue(
                                    category="unmatched-environment",
                                    message=(
                                        f"Mismatched environment: '\\begin{{{opened_name}}}' "
                                        f"closed by '\\end{{{env_name}}}'."
                                    ),
                                    math_content=tex,
                                    display_mode=display,
                                    offset=i,
                                )
                            )
                        else:
                            env_stack.pop()
                        i = next_pos
                        continue
                elif cmd == "left":
                    has_delim, next_pos = _consume_delimiter(tex, j)
                    if not has_delim:
                        issues.append(
                            LaTeXIssue(
                                category="unmatched-delimiter",
                                message="Missing or invalid delimiter after '\\left'.",
                                math_content=tex,
                                display_mode=display,
                                offset=i,
                            )
                        )
                        i = j
                    else:
                        left_stack.append(i)
                        i = next_pos
                    continue
                elif cmd == "right":
                    has_delim, next_pos = _consume_delimiter(tex, j)
                    if not has_delim:
                        issues.append(
                            LaTeXIssue(
                                category="unmatched-delimiter",
                                message="Missing or invalid delimiter after '\\right'.",
                                math_content=tex,
                                display_mode=display,
                                offset=i,
                            )
                        )
                    if not left_stack:
                        issues.append(
                            LaTeXIssue(
                                category="unmatched-delimiter",
                                message="Unexpected '\\right' without matching '\\left'.",
                                math_content=tex,
                                display_mode=display,
                                offset=i,
                            )
                        )
                    else:
                        left_stack.pop()
                    i = next_pos if has_delim else j
                    continue
                elif cmd in _TEXT_MODE_COMMANDS:
                    p = _skip_ws_and_comments(tex, j)
                    if p < n and tex[p] == "{":
                        brace_stack.append(p)
                        text_mode_stack.append(_TextModeFrame(brace_depth=len(brace_stack), in_math=False))
                        i = p + 1
                        continue
                elif cmd in _FRAC_COMMANDS:
                    ok1, p1 = _consume_single_arg(tex, j)
                    ok2, _p2 = _consume_single_arg(tex, p1) if ok1 else (False, j)
                    if not (ok1 and ok2):
                        issues.append(
                            LaTeXIssue(
                                category="latex-syntax",
                                message=f"Command '\\{cmd}' is missing required numerator/denominator arguments.",
                                math_content=tex,
                                display_mode=display,
                                offset=i,
                            )
                        )
                i = j
                continue
            # Escaped single non-letter symbol (\{, \}, \%, \_, \,, \|, \ , etc.)
            i += 2 if i + 1 < n else 1
            continue

        # 3. Braces
        if ch == "{":
            brace_stack.append(i)
            i += 1
            continue

        if ch == "}":
            if not brace_stack:
                issues.append(
                    LaTeXIssue(
                        category="unbalanced-braces",
                        message="Unexpected closing brace '}' with no matching '{'.",
                        math_content=tex,
                        display_mode=display,
                        offset=i,
                    )
                )
            else:
                closing_depth = len(brace_stack)
                atom_scripts.pop(closing_depth, None)
                script_arg_until.pop(closing_depth, None)
                brace_stack.pop()
                if text_mode_stack and text_mode_stack[-1].brace_depth == closing_depth:
                    text_mode_stack.pop()
            i += 1
            continue

        # 4. Nested $ inside \text{...}
        if ch == "$" and text_mode_stack:
            text_mode_stack[-1].in_math = not text_mode_stack[-1].in_math
            i += 1
            continue

        # 5. Subscripts & Superscripts
        if ch in ("_", "^"):
            if in_text_mode:
                if ch == "_":
                    issues.append(
                        LaTeXIssue(
                            category="latex-syntax",
                            message="Unescaped '_' inside \\text{...} causes KaTeX ParseError.",
                            math_content=tex,
                            display_mode=display,
                            offset=i,
                        )
                    )
                i += 1
                continue

            if i >= script_arg_until.get(depth, -1):
                seen = atom_scripts.setdefault(depth, set())
                if ch in seen:
                    kind = "subscript" if ch == "_" else "superscript"
                    issues.append(
                        LaTeXIssue(
                            category="latex-syntax",
                            message=f"Double {kind} '{ch}' on the same base token.",
                            math_content=tex,
                            display_mode=display,
                            offset=i,
                        )
                    )
                else:
                    seen.add(ch)
                arg_end = _skip_script_arg_end(tex, i + 1)
                if arg_end is None:
                    kind = "subscript" if ch == "_" else "superscript"
                    issues.append(
                        LaTeXIssue(
                            category="latex-syntax",
                            message=f"Dangling {kind} operator '{ch}' with missing argument.",
                            math_content=tex,
                            display_mode=display,
                            offset=i,
                        )
                    )
                else:
                    script_arg_until[depth] = arg_end
            i += 1
            continue

        i += 1

    for offset in brace_stack:
        issues.append(
            LaTeXIssue(
                category="unbalanced-braces",
                message="Unclosed opening brace '{' in math expression.",
                math_content=tex,
                display_mode=display,
                offset=offset,
            )
        )

    for env_name, offset in env_stack:
        issues.append(
            LaTeXIssue(
                category="unmatched-environment",
                message=f"Unclosed '\\begin{{{env_name}}}' without matching '\\end{{{env_name}}}'.",
                math_content=tex,
                display_mode=display,
                offset=offset,
            )
        )

    for offset in left_stack:
        issues.append(
            LaTeXIssue(
                category="unmatched-delimiter",
                message="Unclosed '\\left' delimiter without matching '\\right'.",
                math_content=tex,
                display_mode=display,
                offset=offset,
            )
        )

    return issues


def _get_node_env() -> dict[str, str]:
    """Build environment variables ensuring NODE_PATH includes standard KaTeX locations."""
    env = os.environ.copy()
    candidate_paths = [
        os.path.expanduser("~/.npm-global/lib/node_modules"),
        "/home/linuxbrew/.linuxbrew/lib/node_modules",
        "/usr/local/lib/node_modules",
        "/usr/lib/node_modules",
    ]
    current_node_path = env.get("NODE_PATH", "")
    if current_node_path:
        candidate_paths.insert(0, current_node_path)
    env["NODE_PATH"] = os.pathsep.join(p for p in candidate_paths if p)
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


def run_local_katex_verification(
    math_blocks: list[tuple[str, bool]],
    strict_warnings: bool = True,
) -> list[KaTeXDiagnostic]:
    """Validate (math_content, is_display) tuples against local Node.js KaTeX in strict mode.

    Returns an empty list gracefully if `node` or `katex` is unavailable.
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
        const diagnostics = [];
        for (const item of blocks) {
            const warnings = [];
            try {
                katex.renderToString(item.math, {
                    displayMode: item.display,
                    throwOnError: true,
                    strict: (errorCode, errorMsg) => {
                        warnings.push(`${errorCode}: ${errorMsg}`);
                    }
                });
                if (warnings.length > 0) {
                    diagnostics.push({
                        math: item.math,
                        display: item.display,
                        error: '',
                        warnings: warnings
                    });
                }
            } catch (err) {
                diagnostics.push({
                    math: item.math,
                    display: item.display,
                    error: err.message,
                    warnings: warnings
                });
            }
        }
        process.stdout.write(JSON.stringify(diagnostics));
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
            diagnostics: list[KaTeXDiagnostic] = []
            for e in data:
                err_msg = str(e.get("error", ""))
                warns = [str(w) for w in e.get("warnings", [])] if strict_warnings else []
                if err_msg or warns:
                    diagnostics.append(
                        KaTeXDiagnostic(
                            math_content=str(e.get("math", "")),
                            display_mode=bool(e.get("display", False)),
                            error_message=err_msg,
                            warnings=warns,
                        )
                    )
            return diagnostics
        return []
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return []
