"""FoundationGuard: does a shell command run the owner's yes script (fg/ownerok.py --give)? (AI-made, Claude; moved out
of guard.py on 13 Nov 2026 so guard.py can shrink.)

Read in the command's own words (12 Nov, the game's PC: a doc appended with cat <<'EOF' that said "never run
fg/ownerok.py --give" opened the owner's box, though nothing waited for a yes). A here-document fed to cat or tee and a
commit message are data; --give must be on the same line. Reading less here can't let a yes through: --give itself
refuses without the box's fresh note.

Outside review 3 (Claude, 12 Nov, finding 3): python fg/ownerok.py $(printf -- '--%s' give) gave the yes with no box,
because --give wasn't spelled out. Running the yes script with words the kit can't see (a substitution, a variable, a
backtick, xargs, eval, a terminal made for it) or from a program of the helper's own opens the box too.

Outside review 6 (Grok, 13 Nov, finding 7): a full path to the interpreter (/usr/local/bin/python3, C:/Python312/
python.exe, ./venv/bin/python, uv run) opened no box. The kit no longer depends on the interpreter's name: a line that
names ownerok.py with words the kit can't see opens the box whatever word starts it, unless the line plainly reads the
file (cat, grep, git diff and the like).
"""
import os, re
BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

WIDER = lambda k: os.environ.get("FG_BREAK", "") == ""   # as in guard.py: off under any break

OWNER_OK = re.compile(r"\bownerok\.py\b[^|;&]*--give\b")
OWNER_OK_LINE = re.compile(r"\bownerok\.py\b[^|;&\n]*--give\b")
PY_WORD = r"(?:^|[\s;&|(`'\"])(?:py|python[\d.]*|pythonw)(?:\.exe)?['\"]?(?=\s|$)"
OWNER_OK_RUN = re.compile(PY_WORD + r"[^|;&\n]*\bownerok\.py\b[^|;&\n]*"                    # python fg/ownerok.py ...
                          r"|(?:^|[;&|(`'\"]|\$\()\s*[\w./\\:~-]*\bownerok\.py\b[^|;&\n]*"    # ./fg/ownerok.py run itself
                          r"|\b(?:xargs|eval|iex|invoke-expression|script|expect|unbuffer|exec)\b[^|;&\n]*\bownerok\.py\b[^|;&\n]*",
                          re.I | re.M)
OWNER_OK_BUILT = re.compile(r"\$|`|\bgive\b|\b(?:xargs|eval|iex|invoke-expression|script|expect|unbuffer|pty|exec)\b", re.I)
OWNER_OK_CODE = re.compile(r"\b(?:import|from)\s+ownerok\b|\b(?:runpy|exec|__import__|import_module)\b[^\n]*\bownerok\b")
# Review 6, finding 7: any piece of a line that names the script, whatever starts it
NAMED = re.compile(r"[^|;&\n]*\bownerok\.py\b[^|;&\n]*")
READERS = {"cat", "type", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "ag", "sed", "wc", "file",
           "stat", "ls", "dir", "diff", "cmp", "md5sum", "sha1sum", "sha256sum", "get-content", "gc", "select-string",
           "code", "nano", "vim", "vi", "notepad"}
GIT_READS = {"diff", "show", "log", "blame", "status", "grep", "ls-files", "add", "restore", "checkout", "cat-file"}


def _reads(piece):
    """Does this piece of a line plainly read or name the file, not run it? (grep "$X" fg/ownerok.py)"""
    if "$(" in piece or "`" in piece or "<(" in piece:                  # a command inside can run it
        return False
    w = [x.strip("'\"") for x in piece.split()]
    while w and re.fullmatch(r"\w+=\S*", w[0]):                       # X=1 cat ...: a value set for one command
        w = w[1:]
    if not w:
        return True
    first = os.path.basename(w[0].replace("\\", "/")).lower()
    if first.endswith(".exe"):
        first = first[:-4]
    return first in READERS or (first == "git" and len(w) > 1 and w[1].lower() in GIT_READS)


def runs(words, spoken=None):
    """Does the command (comments, harmless parts and here-document data already taken out) run the yes script?"""
    if spoken is not None:
        return bool(OWNER_OK.search(spoken))
    if OWNER_OK_LINE.search(words):
        return True
    if not WIDER("owner_ok_built"):
        return False
    if any(OWNER_OK_BUILT.search(m.group(0)) for m in OWNER_OK_RUN.finditer(words)) or \
            OWNER_OK_LINE.search(re.sub(r"['\"]", "", words)):                       # --gi''ve, --"give"
        return True
    if re.search(PY_WORD, words, re.M) and OWNER_OK_CODE.search(words):              # a Python program loading it
        return True
    if not WIDER("owner_ok_any_runner"):
        return False
    return any(OWNER_OK_BUILT.search(m.group(0)) and not _reads(m.group(0)) for m in NAMED.finditer(words))


AWAY_ON = ("switch away mode ON: until you switch it off, changes to your tests and lists go through without a box "
           "each, and the upload waits for your one yes when you're back")
AWAY_OFF = "switch away mode OFF: each change to a guard asks you at once again"


INSTALL = "the kit's install"                  # the game's PC, 13 Nov: an install fought its own put-back; now it asks


def kit_setting(cmd):
    """(file it writes, what it does, where) for a kit command that writes guard files, in the owner's words."""
    if re.search(r"\bupdate\.py\b", cmd) and not BREAK("update_ask"):
        return INSTALL, "update the kit's own code in fg/ to a newer kit (its settings, hooks and tests stay as they are)", \
            "the kit's own code in fg/"
    if re.search(r"\b(?:install|setup)\.py\b", cmd) and not BREAK("install_ask"):
        return INSTALL, "install or update the kit in this project: its hooks (the guard every AI tool runs before each step), and its own code in fg/ when setup brings a newer kit", \
            "your AI tools' settings, the kit's settings and code, and the other copies of this project"
    if "copies.py" in cmd:
        return ".claude/settings.local.json", "put the kit's guard into the other copies of this project", "each copy's AI tool settings"
    if "away.py" in cmd:
        m = re.search(r"away\.py\b[^|;&\n]*?\b(on|off)\b", cmd)
        on = bool(m) and m.group(1) == "on"
        return "foundationguard.json", AWAY_ON if on else AWAY_OFF, "foundationguard.json"
    return "foundationguard.json", "record in the kit's settings that you locked main on GitHub, in your words", "foundationguard.json"


def read_as(words):
    """The game's PC, 13 Nov: the box asked about taking the guard files when a helper only wrote those words into a note.
    The box quotes what the kit read, so the owner can tell a command from text."""
    return (f" The kit read this in the command: '{words[:120]}'. If that is only text the helper is writing into a file "
            "or a note, say no, and ask it to write the file without those words.")
