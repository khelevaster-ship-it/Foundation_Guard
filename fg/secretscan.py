"""FoundationGuard secret scan (AI-made, Claude, 2026-11-09).

Looks at the lines a push would add and stops it if one holds a password, API key, token or private key.
Run by the push gate (fg/push.py) and by the git pre-push hook, so pushes made by other tools are covered too.
  python fg/secretscan.py                 # scan lines added since the upstream branch (or the last passed commit)
  python fg/secretscan.py --all           # scan every tracked file (first install)
  python fg/secretscan.py --range A..B    # scan lines added between two commits
A false alarm is allowed only by a line in secrets_allow.txt (a guard file: changing it needs the owner's OK):
  <file glob> <a few words that appear on the line>   # reason, owner's words
Secrets belong in environment variables or the engine's own secret store, never in the repository.
"""
import fnmatch, math, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k

# (name, regex): shapes that are secrets on sight
SHAPES = [
    ("AWS access key", r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    ("Slack token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    ("Slack webhook", r"hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]+"),
    ("Discord webhook", r"discord(?:app)?\.com/api/webhooks/\d+/[\w-]{20,}"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("Stripe key", r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}\b"),
    ("Anthropic key", r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI key", r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}"),
    ("SendGrid key", r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}"),
    ("Twilio key", r"\bSK[0-9a-fA-F]{32}\b"),
    ("Hugging Face token", r"\bhf_[A-Za-z0-9]{30,}\b"),
    ("npm token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    ("private key", r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY(?: BLOCK)?-----"),
    ("JSON web token", r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("password in a web address", r"\b[a-z][a-z0-9+.\-]*://[^\s:/@'\"]+:([^\s@/'\"$<{]{3,})@[\w.\-]+"),
]
DOC_EXAMPLES = {"AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"}   # AWS's own documented examples

# a name that says "secret" followed by a written-in value
NAMED = re.compile(r"""(?ix)
    (?P<name>[\w.\-]*(?:passw(?:or)?d|passwd|passphrase|\bpwd\b|\bpass\b(?=["']?\s*[:=]\s*["'])|secret|token|api[_\-]?key|apikey|access[_\-]?key|private[_\-]?key|
             client[_\-]?secret|auth[_\-]?key|auth\b|credentials?|webhook[_\-]?url|conn(?:ection)?[_\-]?string)[\w.\-]*)
    ["']?\s*(?::=|=>|=|:|,)\s*@?\s*(?:[(\[{]\s*)?(?:(?:TEXT|_T|L|u8|tr|_)\(\s*)?
    (?P<q>["'`]?)(?P<val>[^\s"'`,;)\]}]{4,})(?P=q)""")
PLACEHOLDER = re.compile(r"""(?ix)^(?:x+|\*+|\.+|-+|<[^>]*>|\{\{.*\}\}|\$\{.*|\$\(.*|%\w+%|\$\w+|
    your[_\-]?.*|change[_\-]?me|example.*|dummy.*|fake.*|test(?:ing)?|sample.*|placeholder.*|redacted|none|null|nil|true|false|
    todo.*|replace[_\-]?me.*|insert.*here|env.*|os\.environ.*|process\.env.*|getenv.*|environment.*|config.*|settings\..*|
    secrets\..*|vars\..*|input.*|args?\..*|self\..*|this\..*|request\..*|str|string|int|bool|bytes|optional.*|type|\w+\(.*)$""")
CODE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?$")


def entropy(s):
    if not s: return 0.0
    n = len(s); return -sum(c / n * math.log2(c / n) for c in (s.count(ch) for ch in set(s)))


def looks_secret_value(v):
    if PLACEHOLDER.match(v) or v in DOC_EXAMPLES: return False
    if CODE_NAME.match(v) and not re.search(r"\d", v): return False        # a variable or function name, not a value
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", v): return False          # a commit id or file hash
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", v): return False   # a UUID
    if re.fullmatch(r"\d+(\.\d+)?", v): return False                         # a number (a timeout, a length)
    return len(v) >= 6 or entropy(v) >= 2.5


def _shape_hit(name, m, line):
    """True if a known key shape really is a secret here (not a documented example or a look-alike)."""
    if not m or m.group(0) in DOC_EXAMPLES:
        return False
    if name == "AWS access key" and any(d in line for d in DOC_EXAMPLES):
        return False
    if name == "password in a web address" and not looks_secret_value(m.group(1)):
        return False
    return not (name == "OpenAI key" and "sk-ant-" in line)


CODE_WORDS = ("lambda", "None", "True", "False", "not", "and", "or", "if", "for")


def _is_code_value(m, line, val):
    """An unquoted value that is code (a name, a call, a keyword), not a written-in secret."""
    sep = line[m.start("val") - 3:m.start("val")]
    if "," in sep or val.endswith(":") or val in CODE_WORDS:
        return True
    if "(" in val or "::" in val or "->" in val:                     # a function call: the value is read at run time
        return True
    return bool(CODE_NAME.match(val)) and (len(val) < 16 or not re.search(r"\d", val) or entropy(val) < 3.5)


def _named_hit(m, line):
    name, val = m.group("name"), m.group("val")
    if re.search(r"(?i)token(?:type|ize|izer|s?count|kind|s)\b|passage|secretar", name):
        return None
    if not m.group("q") and not BREAK("secrets_named") and _is_code_value(m, line, val):
        return None
    return "a written-in value for '" + name + "'" if looks_secret_value(val) else None


def find(line):
    """A short reason if the line holds a secret, else None."""
    if BREAK("secrets_scan"): return None
    hit = next((name for name, rx in SHAPES if _shape_hit(name, re.search(rx, line), line)), None)
    return hit or next((h for h in (_named_hit(m, line) for m in NAMED.finditer(line)) if h), None)

def allow_rules(root):
    p = os.path.join(root, "secrets_allow.txt"); out = []
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            l = l.split("#", 1)[0].strip()
            if l:
                g, _, words = l.partition(" "); out.append((g, words.strip()))
    return out


def allowed(path, line, rules):
    return any(fnmatch.fnmatch(path, g) and (not w or w in line) for g, w in rules)


BINARY = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".uasset", ".umap", ".wav", ".ogg", ".mp3", ".fbx", ".glb", ".zip", ".ttf", ".otf", ".exr", ".psd")


def added_lines(root, rng):
    """[(path, line)] added in the commit range (A..B), by git diff."""
    p = subprocess.run(["git", "diff", "-U0", "--no-color", "--no-ext-diff", rng], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out, path = [], None
    for l in p.stdout.splitlines():
        if l.startswith("+++ "):
            path = l[6:] if l.startswith("+++ b/") else None
        elif l.startswith("+") and path and not path.lower().endswith(BINARY):
            out.append((path, l[1:]))
    return out


def tracked_lines(root):
    files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.splitlines()
    out = []
    for f in files:
        if f.lower().endswith(BINARY): continue
        try:
            with open(os.path.join(root, f), encoding="utf-8", errors="strict") as fh:
                out += [(f, l.rstrip("\n")) for l in fh]
        except (OSError, UnicodeDecodeError):
            continue
    return out


def scan(root, pairs):
    rules = allow_rules(root); hits = []
    for path, line in pairs:
        if path in ("secrets_allow.txt",) or len(line) > 4000: continue
        if (path.startswith("fg/") or path.startswith("tests/test_kit.py")) and not BREAK("secrets_kit"): continue   # the kit's own code
        r = find(line)
        if r and not allowed(path, line, rules):
            hits.append((path, r))
    return hits


def default_range(cfg):
    root = cfg["_root"]
    up = subprocess.run(["git", "rev-parse", "--verify", "-q", "@{upstream}"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    if up: return up + "..HEAD"
    import steps as SP
    last = SP.passed(cfg)                              # review 6: only a pass the kit recorded (F265)
    if last: return last + "..HEAD"
    return None


def push_range(root, local_sha, remote_sha):
    """The commit range a pre-push would send: remote..local, or (new branch) from where it left the remote's branches."""
    if not set(remote_sha) <= {"0"}: return remote_sha + ".." + local_sha
    for ref in ("origin/HEAD", "origin/main", "origin/master"):
        mb = subprocess.run(["git", "merge-base", ref, local_sha], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
        if mb: return mb + ".." + local_sha
    return None


def report(hits):
    if not hits: return "SECRETS none found in the added lines"
    seen = []
    for h in hits:
        if h not in seen: seen.append(h)
    return ("SECRETS FAIL: " + str(len(seen)) + " line(s) look like a password, key or token. Take it out, put it in an "
            "environment variable, and change (rotate) the key if it was ever pushed:\n  " +
            "\n  ".join(f"{p}: {r}" for p, r in seen[:20]) +
            "\n  (A false alarm? The owner can allow it with a line in secrets_allow.txt.)")


def check(cfg, rng=None):
    root = cfg["_root"]
    rng = rng or default_range(cfg)
    pairs = added_lines(root, rng) if rng else tracked_lines(root)
    hits = scan(root, pairs)
    return not hits, report(hits)


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    import config as C
    cfg = C.load(); a = sys.argv[1:]
    if "--all" in a:
        hits = scan(cfg["_root"], tracked_lines(cfg["_root"])); ok, msg = not hits, report(hits)
    else:
        ok, msg = check(cfg, a[a.index("--range") + 1] if "--range" in a else None)
    print(msg); sys.exit(0 if ok else 1)
