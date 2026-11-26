"""FoundationGuard: the owner's box in three plain sentences (AI-made, Claude, 2026-11-16).
The owner, 16 Nov: "i have no idea for the most part what i am oking or not" (82 boxes in a day). Every box now opens with
what changes, what could go wrong and the kit's recommendation; the kit's longer reasons follow as details."""
import os

BREAK = lambda name: os.environ.get("FG_BREAK", "") == name


def _kind(f):
    try:
        import ownerok as OK
        return OK._kind(str(f))
    except Exception:
        return "a file that guards your project"


def _frame(rule, f, weaker):
    """(what changes, what could go wrong, recommendation) for one box, by the rule that raised it."""
    r = rule or ""
    if r.startswith("a push without the gate"):
        return ("one push goes up without any of the checks",
                "a broken or weakened change could reach the shared copy",
                "No, unless the guard itself is wrongly blocking and you want this pushed anyway")
    if r.startswith("the owner's yes"):
        return ("the upload carries changes the helper made to the files that guard your project",
                "those checks may catch less from now on",
                "Yes if you asked for this work; otherwise No, and ask the helper to put it back")
    if r.startswith("the accepted state"):
        return ("the kit takes the guard files as they are now as the state it keeps",
                "a change no one approved would become the new normal",
                "Yes only if you changed them yourself")
    if r.startswith("the AI tool's own settings"):
        return ("your AI tool stops asking before routine edits, reading, building and testing",
                "fewer chances to stop a helper by hand, though the kit still checks everything",
                "Yes if you want helpers to keep working without you at every step")
    if r.startswith("a kit command"):
        return ("a kit command changes how the guard works in this project",
                "the guard could cover less than before",
                "Yes if you asked for it; otherwise No")
    if r.startswith(("a kit part switched", "several kit parts")):
        return ("a part of the kit is switched", "a check could be turned down or off" if weaker else
                "little: nothing is turned down", "No, unless you asked for it" if weaker else "Yes if you asked for it")
    if r.startswith("a record re-recorded"):
        return ("a frozen limit or list the checks compare against is recorded again",
                "if any number goes up or anything new is let in, a check gets weaker",
                "No, unless you asked for exactly this")
    what = (f"the helper runs a change the kit can't fully read {f}" if str(f).startswith("(")
            else f"the helper may change '{f}' ({_kind(f)}): a write in this command lands where the kit can't tell"
            if "can't tell where it lands" in r and not BREAK("variable_write_words")
            else f"the helper changes '{f}' ({_kind(f)})")
    if weaker:
        return (what, "the kit thinks this makes a check weaker, so a real problem could slip past it",
                "No, unless you asked for exactly this; ask the helper why first")
    return (what, "a check that protects your project could catch less, though the kit saw no sign of that",
            "Yes if it's part of the work you asked for; otherwise No")


def lead(rule, f, weaker):
    """The three sentences that open every box."""
    if BREAK("box_three"):
        return ""
    c, risk, rec = _frame(rule, f, weaker)
    return f"WHAT CHANGES: {c}. WHAT COULD GO WRONG: {risk}. MY RECOMMENDATION: {rec}. Details: "


# ---- The question in the chat before the box opens (beta gate line 1; Plan 2 PR 9; the owner, 19 Nov) ----------------
# The owner, 19 Nov: "it is not an easy task to scroll the little box slow enough to read it all without skipping".
# The AI tool's own box is a small scrolling field. So, with "chat_first": true, the first try at a step that needs a
# box stops the helper once, with the question to post in the chat as an ordinary message. The kit then looks for those
# sentences in the session's own record (the transcript the tool hands every hook) and only then opens the box, which
# is short and points up at the chat. The helper is the party that wants the yes, so the kit never takes its word that
# it posted: unseen twice, the box opens anyway and says the chat copy could not be seen.
CHAT_MINUTES, CHAT_TRIES, CHAT_TAIL = 15, 3, 2000000
CHAT_HEAD = "FoundationGuard has a question for you"
# The game's PC, 19 Nov: its helper works from a project thread, where the owner reads only what a message tool sends;
# the lines went out through send_message, the kit looked only at plain text, and the box opened "unseen" at try three.
CHAT_TOOLS = r"(^|_)(send|post)_?(user_?)?message$|(^|_)message_(user|owner)$|(^|_)notify_user$"


def chat_lines(rule, f, weaker):
    c, risk, rec = _frame(rule, f, weaker)
    return [f"What changes: {c}.", f"What could go wrong: {risk}.", f"The kit recommends: {rec}."]


def _squash(t):
    return " ".join(str(t).replace("*", "").replace("_", "").replace("`", "").split())


def _strings(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        v = list(v.values())
    return [s for x in v for s in _strings(x)] if isinstance(v, list) else []


def in_chat(transcript, lines, tools=()):
    """True when the helper's own messages in this session's record hold every one of these sentences: as plain text,
    or as the words of a tool whose job is to send the owner a message (never inside a command or a file being
    written). None when there is no record to read."""
    import json, re
    pats = [] if BREAK("chat_message_tools") else [CHAT_TOOLS] + list(tools or [])
    sends = lambda b: (b.get("type") == "tool_use" and isinstance(b.get("name"), str)
                       and any(re.search(p, b["name"], re.I) for p in pats))
    try:
        with open(transcript, "rb") as fh:
            fh.seek(0, 2); size = fh.tell(); fh.seek(max(0, size - CHAT_TAIL))
            rows = fh.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return None
    said = []
    for row in rows:
        try:
            j = json.loads(row)
        except ValueError:
            continue
        m = j.get("message") if isinstance(j, dict) else None
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        content = m.get("content")
        if isinstance(content, str):
            said.append(content)
        for b in content if isinstance(content, list) else []:
            if isinstance(b, dict):
                said += [b.get("text", "")] if b.get("type") == "text" else _strings(b.get("input")) if sends(b) else []
    text = _squash(" ".join(said))
    return all(_squash(l) in text for l in lines)


def _book(cfg):
    import steps as SP
    return os.path.join(SP._home(cfg), "chat_first.json")


def chat_first(cfg, rule, f, weaker, details, transcript=None, now=None):
    """(stop, note). stop: the words that stop the helper this once so the question reaches the chat, else None.
    note: when the box may open, what it says about the chat copy ("seen", "unseen", "told")."""
    import hashlib, json, time
    now = now or time.time()
    lines = chat_lines(rule, f, weaker)
    key = hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]
    path = _book(cfg)
    try:
        book = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        book = {}
    book = {k: v for k, v in book.items() if isinstance(v, dict) and now - v.get("t", 0) < CHAT_MINUTES * 60}
    had = book.get(key)
    seen = (True if BREAK("chat_unchecked") else in_chat(transcript, lines, cfg.get("chat_tools"))) if had else None
    note = None
    if had and seen:
        note = "seen"
    elif had and seen is None:
        note = "told"                                  # no record to read (another AI tool): the helper was told once
    elif had and had.get("n", 1) + 1 >= CHAT_TRIES and not BREAK("chat_holds_back"):
        note = "unseen"
    if note or BREAK("chat_first"):
        book.pop(key, None)
    else:
        book[key] = {"t": had["t"] if had else now, "n": (had.get("n", 1) + 1) if had else 1}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(book, open(path, "w", encoding="utf-8"))
    except OSError:
        return None, "told"                            # can't keep count: never stop the helper for ever
    if note or BREAK("chat_first"):
        return None, note or "told"
    again = ("The owner's chat doesn't show the question yet. " if had else "")
    return (again + "Before the owner is asked, they must be able to read the question, and the box is too small for it. "
            "Post the lines below to the owner now, word for word, each on its own line: as an ordinary chat message "
            "of your own (plain text, not inside a command), or, where the owner reads only what a message tool sends, "
            "with that tool. Then run the same step again, unchanged: the box opens then.\n\n"
            + CHAT_HEAD + "\n" + "\n".join(lines) + "\nDetails from the kit: " + " ".join(str(details).split())
            + "\nA box with Allow and Deny opens next."), None


CHAT_BOX = 360    # the longest box once the question went to the chat: it must be readable without scrolling


def short(rule, f, weaker, note):
    """The box once the question went to the chat: short enough to read without scrolling, whether or not the kit
    could see the chat copy (the owner, 19 Nov, on the long box at the third try: "this does not at all fix the
    issue")."""
    c, risk, rec = _frame(rule, f, weaker)
    c = c if len(c) <= 80 else c[:77].rstrip() + "..."
    return f"WHAT CHANGES: {c}. RECOMMENDED: {rec}. {WHERE[note]}"


WHERE = {"seen": "Full question: in the chat above.",
         "unseen": "Full question: in the chat above (if it isn't, press Deny and ask the helper).",
         "told": "The helper was told to put this question in the chat first; the kit can't see this tool's chat, so the "
                 "whole question is here too."}
