"""FoundationGuard adapters for other AI coding tools (AI-made, Claude, 2026-11-09).

The command guard (fg/guard.py) was written for Claude Code's hook. GitHub Copilot CLI, OpenAI Codex CLI and Cursor have
hooks too, but each sends its own JSON and wants its own answer. This file turns each one's input into the shape the
guard reads, and turns the guard's answer back into each one's words. Formats from each tool's own hook pages, read
9 Nov 2026:
  Copilot CLI  .github/hooks/*.json, event preToolUse; input toolName + toolArgs (camelCase) or tool_name + tool_input;
               answer {"permissionDecision": "deny"|"ask", "permissionDecisionReason": ...}; exit 2 also denies.
  Codex CLI    .codex/hooks.json, event PreToolUse; input tool_name ("Bash", "apply_patch") + tool_input.command;
               answer hookSpecificOutput.permissionDecision "deny" ("ask" is NOT supported: the call goes ahead).
  Cursor       .cursor/hooks.json, events beforeShellExecution (input "command", "cwd") and preToolUse (tool_name
               "Shell"/"Write"/"Delete", tool_input); answer {"permission": "deny"|"ask", "user_message", "agent_message"}.
               "ask" is not enforced for preToolUse, so a guard-file change there is denied.
Where a tool can't ask the owner, a guard-file change is refused with a reason that says the owner must make or approve
it. Refusing is the safe side: the helper can't get round it by being agreeable.
"""
import json, os, re

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
AGENTS = ("claude", "copilot", "codex", "cursor")
SHELL = {"bash", "powershell", "shell", "exec_command", "run_terminal_cmd", "terminal"}
WRITE = {"write", "create", "edit", "str_replace_editor", "str_replace", "multiedit", "delete", "notebookedit"}
ASK_WORKS = {("claude", "any"), ("copilot", "any"), ("cursor", "shell")}     # where "ask" really stops and asks the owner


def _obj(x):
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except ValueError:
            return {"command": x}
    return x if isinstance(x, dict) else {}


def detect(data, flag=None):
    if flag in AGENTS:
        return flag
    if "toolName" in data or "toolArgs" in data:
        return "copilot"
    if "cursor_version" in data or "conversation_id" in data:
        return "cursor"
    if "turn_id" in data or data.get("tool_name") == "apply_patch":
        return "codex"
    return "claude"


PATCH_FILE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$")


def patch_files(text):
    """[(path, old, new)] from a Codex apply_patch body: removed lines are the old text, added lines the new."""
    out, cur = [], None
    for line in (text or "").split("\n"):
        m = PATCH_FILE.match(line.strip())
        if m:
            cur = [m.group(2).strip(), [], [], m.group(1)]; out.append(cur); continue
        if cur and line.startswith("+") and not line.startswith("+++"):
            cur[2].append(line[1:])
        elif cur and line.startswith("-") and not line.startswith("---"):
            cur[1].append(line[1:])
    return [(p, "\n".join(o) or ("(whole file)" if kind == "Delete" else ""), "\n".join(n)) for p, o, n, kind in out]


def _edit_input(ti):
    """A write/edit tool's arguments in Claude Code's Write/Edit shape."""
    path = ti.get("file_path") or ti.get("path") or ti.get("filePath") or ti.get("target_file") or ""
    new = ti.get("content") or ti.get("contents") or ti.get("file_text") or ti.get("new_string") or ti.get("new_str") or ""
    old = ti.get("old_string") or ti.get("old_str") or ""
    return ("Edit" if old else "Write"), {"file_path": path, "old_string": old, "new_string": new, "content": new}


def _cwd(data):
    return data.get("cwd") or (data.get("workspace_roots") or [None])[0] or os.getcwd()


def _patch_calls(ti):
    body = ti.get("command") or ti.get("patch") or ti.get("input", "")
    return [("Edit", {"file_path": p, "old_string": o, "new_string": n}) for p, o, n in patch_files(body)] or [("Bash", {"command": ""})]


def _calls(name, ti):
    low = name.lower()
    if low == "apply_patch":
        return _patch_calls(ti)
    if low in SHELL:
        return [("Bash", {"command": ti.get("command") or ti.get("cmd") or ""})]
    if low in WRITE:
        return [_edit_input(ti)]
    return [(name or "Bash", ti)]


def normalise(agent, data):
    """([(tool, tool_input)], cwd) in Claude Code's shape. One Codex patch can touch several files."""
    if BREAK("agents_" + agent):
        return [(data.get("tool_name") or "Bash", data.get("tool_input") or {})], data.get("cwd") or os.getcwd()
    if agent == "cursor" and data.get("hook_event_name") == "beforeShellExecution":
        return [("Bash", {"command": data.get("command", "")})], _cwd(data)
    ti = _obj(data.get("toolArgs") if "toolArgs" in data else data.get("tool_input"))
    return _calls(str(data.get("toolName") or data.get("tool_name") or ""), ti), ti.get("working_directory") or _cwd(data)


def _claude_ask(text):
    out = {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": text}
    return {"hookSpecificOutput": out}


def _codex_deny(text):
    out = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": text}
    return {"hookSpecificOutput": out}


CANT_ASK = (" This AI tool can't ask you, so the change is refused: make it yourself, or tell the helper in your own words "
            "and let it use the kit's approve step.")


# 11 Nov (an unattended session stopped five times in ten minutes; its owner was on a phone): every question the kit
# asks is one line that says what is asked, why ("Why: ..."), and the one thing to click.
ASK_ACTION = " To answer: choose Yes (allow) to let it go ahead, or No (deny) to stop it."


def one_line(kind, reason):
    """The kit's words for the owner, in one line; a question ends with what to click."""
    if BREAK("ask_one_line"):
        return reason
    text = " ".join(str(reason).split())
    return text + ASK_ACTION if kind == "ask" and not text.endswith(ASK_ACTION.strip()) else text


def asks(agent, shell=True):
    """True where this AI tool really stops and asks the owner."""
    return (agent, "any") in ASK_WORKS or (agent, "shell" if shell else "edit") in ASK_WORKS


def answer(agent, kind, reason, shell=True):
    """(stdout text or '', exit code) for 'block' or 'ask' in the tool's own words."""
    if kind == "ask" and (agent, "any") not in ASK_WORKS and (agent, "shell" if shell else "edit") not in ASK_WORKS:
        kind, reason = "block", reason + CANT_ASK
    reason = one_line(kind, reason)
    text, deny = ("FoundationGuard: " if not BREAK("kit_label") else "") + reason, kind == "block"
    if agent == "copilot":
        return json.dumps({"permissionDecision": "deny" if deny else "ask", "permissionDecisionReason": text}), 0
    if agent == "codex":
        return json.dumps(_codex_deny(text)), 2
    if agent == "cursor":
        return json.dumps({"continue": True, "permission": "deny" if deny else "ask", "user_message": text, "agent_message": text}), 0
    return ("", 2) if deny else (json.dumps(_claude_ask(text)), 0)


def _top(fg):
    import paths as P
    return P.from_top("$(git rev-parse --show-toplevel)", fg)


def hook_files(fg, py):
    """{path: json} for each tool's project hook file, calling fg/guard.py with --agent."""
    g = lambda a: f"{py} {fg}/guard.py --agent {a}"
    return {
        ".github/hooks/foundationguard.json": {"version": 1, "hooks": {"preToolUse": [
            {"type": "command", "bash": f"{py} {fg}/guard.py --agent copilot",
             "powershell": f"& {py} {fg}/guard.py --agent copilot", "cwd": ".", "timeoutSec": 30}]}},
        ".codex/hooks.json": {"hooks": {"PreToolUse": [{"matcher": "Bash|apply_patch|Edit|Write", "hooks": [
            {"type": "command", "command": f"{py} \"{_top(fg)}/guard.py\" --agent codex",
             "timeout": 30, "statusMessage": "FoundationGuard check"}]}]}},
        ".cursor/hooks.json": {"version": 1, "hooks": {
            "beforeShellExecution": [{"command": g("cursor"), "failClosed": True}],
            "preToolUse": [{"command": g("cursor"), "matcher": "Write|Delete", "failClosed": True}]}}}


RULES_HEAD = ("<!-- Written by FoundationGuard from CLAUDE.md (AI-made). Edit CLAUDE.md, then run: python fg/agents.py --rules -->\n")


def rules_files(claude_md):
    """{path: text}: the same helper rules for tools that read AGENTS.md, Copilot's instructions file or Cursor's rules."""
    body = RULES_HEAD + claude_md.strip() + "\n"
    return {"AGENTS.md": body, ".github/copilot-instructions.md": body,
            ".cursor/rules/foundationguard.mdc": "---\ndescription: The project's rules for AI helpers\nalwaysApply: true\n---\n" + body}


def write_all(root, fg, py, only_missing=False):
    """Write the hook and rules files; returns the paths written."""
    if BREAK("agents_files"):
        return []
    done = []
    for p, j in hook_files(fg, py).items():
        full = os.path.join(root, p); os.makedirs(os.path.dirname(full), exist_ok=True)
        old = json.load(open(full, encoding="utf-8-sig")) if os.path.exists(full) else {}
        merged = _merge(old, j)
        json.dump(merged, open(full, "w", encoding="utf-8"), indent=2); done.append(p)
    src = os.path.join(root, "CLAUDE.md")
    if os.path.exists(src):
        for p, t in rules_files(open(src, encoding="utf-8").read()).items():
            full = os.path.join(root, p)
            if os.path.exists(full) and not open(full, encoding="utf-8").read().startswith(RULES_HEAD):
                continue                                         # the project's own file: never overwritten
            os.makedirs(os.path.dirname(full) or root, exist_ok=True)
            open(full, "w", encoding="utf-8").write(t); done.append(p)
    return done


def _merge(old, new):
    """Add the kit's hook entries to a tool's existing hook file without removing anything already there."""
    out = dict(old or {}); out.setdefault("version", new.get("version")) if "version" in new else None
    hooks = out.setdefault("hooks", {})
    for ev, entries in new["hooks"].items():
        have = hooks.setdefault(ev, [])
        if not BREAK("agents_respell"):              # 13 Nov: the kit's own older call (no -I) is replaced, not doubled
            have[:] = [h for h in have if h in entries or "guard.py" not in json.dumps(h) or "--agent" not in json.dumps(h)]
        for e in entries:
            if e not in have:
                have.append(e)
    return {k: v for k, v in out.items() if v is not None}


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))     # the kit's own Python has no other way to find these
    import paths as P
    root = os.getcwd(); fg = P.kit_dir(root)
    import config as C
    py = C.hook_python()
    for p in write_all(root, fg, py):
        print("wrote " + p)
