"""FoundationGuard function finder for C-family languages (AI-made, Claude, 2026-11-09).

Block-based, not one-line patterns: every "{" at bracket depth 0 opens a block, and the text since the last ; { or }
(its header, over as many lines as it takes) says what the block is. Headers with a parameter list are functions:
plain, member (A::B), trailing return (-> T), constructor init lists, Java/C# annotations and attributes, TS decorators,
arrow functions and lambdas assigned to a name, Go func with a receiver. Class, namespace, control and initializer
blocks are not. Nested functions (lambdas inside a function) belong to the function around them.
Also: clean_lines() blanks comments, strings (incl. multi-line raw strings and template literals) and #if 0 blocks.
"""
import os, re

CONTROL = re.compile(r"^(if|else|for|foreach|while|do|switch|try|catch|finally|using|lock|synchronized|unsafe|fixed|checked|"
                     r"unchecked|return|throw|case|default|new|await|yield|select|go|defer|with)\b")
SCOPE = re.compile(r"(^|\s)(class|struct|interface|enum|namespace|record|union|module|object|trait|impl|extern|package)\b")
MODS = re.compile(r"^(?:(?:@[\w.]+(?:\([^()]*(?:\([^()]*\)[^()]*)*\))?|\[[^\[\]]*\]|[A-Z][A-Z0-9_]{2,}\s*\([^()]*(?:\([^()]*(?:\([^()]*\)[^()]*)*\)[^()]*)*\))\s*)+")


_BRK = lambda k: os.environ.get("FG_BREAK", "") == k
JS_EXT = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx")      # JavaScript and TypeScript (web pack, 11 Nov)
HTML_EXT = (".html", ".htm")
NO_RAW_R = (".py", ".cs", ".java") + JS_EXT + HTML_EXT


def _verbatim_end(s, j, n):
    """Index of the closing quote of a C# verbatim string ("" is an escaped quote), or n."""
    while j < n and not (s[j] == '"' and not s.startswith('""', j)):
        j += 2 if s.startswith('""', j) else 1
    return j


PLAIN = re.compile(r"[^\"'#/$@`]*")                # only these characters can start a comment, a string or a template
PLAIN_HOLE = re.compile(r"[^\"'#/$@`{}]*")         # inside a JS ${...} hole its braces count too


class _Cleaner:
    """Reads lines one by one, keeping what runs on between lines: block comments, raw strings, verbatim strings,
    template literals and #if 0 blocks. Each step below looks at position i and returns the next position, or None
    when it doesn't apply; returning n (the line length) ends the line."""
    def __init__(self, ext):
        self.ext, self.c, self.raw, self.verb, self.tpl, self.if0 = ext, False, None, False, False, 0
        self.holes = []                                       # open ${...} holes of JS templates: brace depth in each
        self.js = ext in JS_EXT and not _BRK("web_reading")
        self.gd = ext == ".gd" and not _BRK("engine_gd")

    def preprocessor(self, s):
        """True when the line is inside (or opens) an #if 0 block, so it is blanked."""
        if self.if0:
            m = re.match(r"^\s*#\s*(if|ifdef|ifndef|endif|else|elif)\b", s)
            if m:
                self.if0 += 1 if m.group(1).startswith("if") else (-1 if m.group(1) == "endif" else 0)
                if m.group(1) in ("else", "elif") and self.if0 == 1: self.if0 = 0
            return True
        if re.match(r"^\s*#\s*if\s+0\b", s):
            self.if0 = 1
            return True
        return False

    # --- states that run on from the line before ---
    def in_comment(self, s, i, n, res):
        if not self.c:
            return None
        j = s.find("*/", i)
        if j < 0: return n
        self.c = False; return j + 2

    def in_raw(self, s, i, n, res):
        if self.raw is None:
            return None
        j = s.find(self.raw, i)
        if j < 0: return n
        k = j + len(self.raw); self.raw = None; return k

    def in_verb(self, s, i, n, res):
        if not self.verb:
            return None
        j = _verbatim_end(s, i, n)
        if j >= n: return n
        self.verb = False; return j + 1

    def in_tpl(self, s, i, n, res):
        if not self.tpl:
            return None
        if self.js:
            return self._tpl_text(s, i, n, res)
        j = s.find("`", i)
        if j < 0: return n
        self.tpl = False; return j + 1

    # --- things that start at position i ---
    def gd_text(self, s, i, n, res):
        if not (self.gd and (s.startswith('"""', i) or s.startswith("'''", i))):
            return None
        q = s[i:i + 3]; end = s.find(q, i + 3)
        if end < 0: self.raw = q; return n               # a GDScript text block runs on over lines
        return end + 3

    def line_comment(self, s, i, n, res):
        c, ext = s[i], self.ext
        if (self.gd and c == "#") or (s.startswith("//", i) and ext != ".gd") or (c == "#" and ext == ".py"):
            return n
        if s.startswith("/*", i) and ext != ".gd":
            self.c = True; return i + 2
        return None

    def raw_r(self, s, i, n, res):
        if not (s[i] == '"' and i > 0 and s[i - 1] == "R" and self.ext not in NO_RAW_R):
            return None
        k = s.find("(", i)
        if k > i and k - i <= 17:
            self.raw = ")" + s[i + 1:k] + '"'; return k + 1
        return None

    def cs_triple(self, s, i, n, res):
        if not (self.ext == ".cs" and (s.startswith('"""', i) or (s[i] == "$" and '"""' in s[i:i + 5]))):
            return None
        q = s.find('"""', i); end = s.find('"""', q + 3)
        if end < 0: self.raw = '"""'; return n
        return end + 3

    def cs_verbatim(self, s, i, n, res):
        if not (self.ext == ".cs" and s.startswith(('@"', '$@"', '@$"'), i)):
            return None
        j = _verbatim_end(s, s.find('"', i) + 1, n)
        if j >= n and not _BRK("design_round2"):
            self.verb = True                                  # a verbatim string runs on to the next line
        return j + 1

    def template(self, s, i, n, res):
        if not (s[i] == "`" and (self.ext in JS_EXT or self.ext == ".go")):
            return None
        if self.js:
            self.tpl = True; return self._tpl_text(s, i + 1, n, res)
        j = s.find("`", i + 1)
        if j < 0: self.tpl = True; return n
        return j + 1

    def _tpl_text(self, s, j, n, res):
        """Inside a JS template's text: returns where code starts again, after the closing ` or inside a ${...} hole
        (web pack, 11 Nov: `${Math.sin(t)}` is code, and a hole may hold another template)."""
        while j < n:
            if s[j] == "\\":
                j += 2; continue
            if s[j] == "`":
                self.tpl = False; return j + 1
            if s.startswith("${", j):
                self.tpl = False; self.holes.append(0); res.append(" "); return j + 2
            j += 1
        return n

    def js_hole(self, s, i, n, res):
        """Braces inside a ${...} hole; the } that closes the hole goes back to the template's text."""
        if not self.holes or s[i] not in "{}":
            return None
        if s[i] == "{" or self.holes[-1]:
            self.holes[-1] += 1 if s[i] == "{" else -1; res.append(s[i]); return i + 1
        self.holes.pop(); self.tpl = True; res.append(" "); return i + 1

    def js_regex(self, s, i, n, res):
        """A JS regex literal such as /"/g or /[{]/ is text, not code (web pack, 11 Nov: the quote in /"/g hid every
        function after it). A / starts one where a value is expected: after ( , = : [ ! & | ? { } ; + - * % ~ ^,
        a word such as return, or at the start of the line; it must close on the same line."""
        if s[i] != "/" or not self.js or not _value_expected(s[:i].rstrip()):
            return None
        j = _regex_close(s, i + 1, n)
        if j >= n or j == i + 1:
            return None
        j += 1
        while j < n and s[j].isalpha():
            j += 1
        return j

    def cs_interpolated(self, s, i, n, res):
        """C# $"..{code}..": the holes are code, the rest is text."""
        if not (s[i] == '"' and self.ext == ".cs" and i > 0 and s[i - 1] == "$" and not _BRK("engine_round1")):
            return None
        j, d = i + 1, 0
        while j < n and not (s[j] == '"' and d == 0):
            j, d = _hole_step(s, j, d, res)
        return j + 1

    def quoted(self, s, i, n, res):
        c = s[i]
        if c not in "\"'":
            return None
        if c == "'" and self.ext in (".rs",) and re.match(r"'[a-z_]\w*[^']", s[i:i + 4]):
            res.append(c); return i + 1                     # a Rust lifetime, not a char
        j = i + 1
        while j < n and s[j] != c:
            j += 2 if s[j] == "\\" else 1
        return j + 1

    STEPS = ("in_comment", "in_raw", "in_verb", "in_tpl", "gd_text", "line_comment", "raw_r", "cs_triple", "cs_verbatim",
             "template", "js_hole", "js_regex", "cs_interpolated", "quoted")

    def line(self, s):
        if self.preprocessor(s):
            return ""
        res, i, n = [], 0, len(s)
        steps = [getattr(self, k) for k in self.STEPS]
        fast = not _BRK("cleaner_fast")
        while i < n:
            if fast and not (self.c or self.raw is not None or self.verb or self.tpl):
                m = (PLAIN_HOLE if self.holes else PLAIN).match(s, i)   # 27 Nov: the game's PC measured 3,000 files
                if m.end() > i:                                        # char by char (77 s); a run of characters no
                    res.append(m.group()); i = m.end(); continue       # step looks at is copied in one go
            nxt = next((r for r in (st(s, i, n, res) for st in steps) if r is not None), None)
            if nxt is None:
                res.append(s[i]); nxt = i + 1
            i = nxt
        return "".join(res)


REGEX_WORDS = r"(?:^|[^\w$])(?:return|typeof|case|do|else|in|of|new|delete|void|throw|yield|await)$"
JS_TYPES = ("", "module", "text/javascript", "application/javascript", "text/babel", "text/jsx")
SCRIPT_TAG = re.compile(r"<script\b([^>]*)>", re.I)


def _value_expected(before):
    return not before or before[-1] in "(,=:[!&|?{};+-*%~^" or re.search(REGEX_WORDS, before) is not None


def _regex_close(s, j, n):
    """Index of the / that closes a regex whose text starts at j (a / inside [...] doesn't close it), or n."""
    cls = False
    while j < n and not (s[j] == "/" and not cls):
        cls = (cls or s[j] == "[") and s[j] != "]"
        j += 2 if s[j] == "\\" else 1
    return j


def html_scripts(lines):
    """An HTML page's own <script> code, line for line, with everything else blanked (web pack, 11 Nov: a single-file
    game keeps all its code in index.html). Scripts with src= and non-JavaScript types (JSON, templates) are left out."""
    text = "\n".join(lines); low = text.lower(); out, last = [], 0
    for m in SCRIPT_TAG.finditer(text):
        typ = re.search(r"\btype\s*=\s*[\"']?([^\"'\s>]*)", m.group(1), re.I)
        if m.start() < last or re.search(r"\bsrc\s*=", m.group(1), re.I) or (typ and typ.group(1).lower() not in JS_TYPES):
            continue
        end = low.find("</script", m.end()); end = len(text) if end < 0 else end
        out += [re.sub(r"[^\n]+", "", text[last:m.end()]), text[m.end():end]]; last = end
    out.append(re.sub(r"[^\n]+", "", text[last:]))
    return "".join(out).split("\n")


def _hole_step(s, j, d, res):
    """One character of a C# interpolated string: (next index, hole depth)."""
    if d == 0 and (s[j] == "\\" or s.startswith("{{", j)):
        return j + 2, d
    if s[j] == "{":
        res.append(" " if d == 0 else "{"); return j + 1, d + 1
    if s[j] == "}" and d > 0:
        res.append(" " if d == 1 else "}"); return j + 1, d - 1
    if d > 0:
        res.append(s[j])
    return j + 1, d


_CLEAN = {}


def clean_lines(lines, ext=""):
    """Comment-, string- and #if 0-free copy of the lines (same count). Keeps braces of code only. The size check
    cleans each file several times over (blocks, functions, imports, boundaries), so one run remembers each answer."""
    key = (ext, os.environ.get("FG_BREAK", ""), "\n".join(lines))
    if key in _CLEAN:
        return list(_CLEAN[key])
    cl = _Cleaner(ext)
    out = [cl.line(ln) for ln in lines]
    if len(_CLEAN) > 20000:
        _CLEAN.clear()
    _CLEAN[key] = tuple(out)
    return out

KT_VAL = re.compile(r"^(?:(?:private|public|internal|protected|override|open|lazy|static)\s+)*(?:val|var|let)\s+([A-Za-z_]\w*)\b.*=\s*$")
NOT_NAMES = ("if", "for", "while", "switch", "catch", "return", "sizeof", "decltype", "new", "throw", "alignas", "static_assert")


def _special_name(h, ext):
    """Kotlin/Swift `val x = {` lambdas and C# property accessors. Returns the name, or None."""
    if _BRK("structure_round3"):
        return None
    if ext in (".kt", ".kts", ".swift", ".scala"):
        m = KT_VAL.match(h)
        if m:
            return m.group(1)                         # val gust: (A) -> B = { a -> ... }  is a function
    if ext == ".cs" and h in ("get", "set", "init", "add", "remove"):
        return h                                      # a property accessor is a function (named by its property below)
    return None


def _value_name(pre):
    """x = (...) => {  /  x = [&](...) {  /  x: function (...) {. Returns (applies?, name)."""
    if re.search(r"=\s*(async\s+)?$", pre) or re.search(r"=\s*\[[^\]]*\]\s*$", pre):
        m = re.search(r"([A-Za-z_$][\w$]*)\s*(?::[^=]*)?=\s*(?:async\s+)?(?:\[[^\]]*\]\s*)?$", pre)
        return True, (m.group(1) if m else None)
    if re.search(r"\bfunction\s*\*?\s*$", pre):                                         # function (...) { as a value
        m = re.search(r"([A-Za-z_$][\w$]*)\s*[:=]\s*(?:async\s+)?function\s*\*?\s*$", pre)
        return True, (m.group(1) if m else None)
    return False, None


def _close_of(text, start, open_ch="(", close_ch=")"):
    """Index of the bracket that closes the one at start, or None."""
    depth = 0
    for k in range(start, len(text)):
        depth += text[k] == open_ch; depth -= text[k] == close_ch
        if depth == 0:
            return k
    return None


def _go_name(h):
    """Go: func (r *T) Name(."""
    rest = h[4:].lstrip()
    if rest.startswith("("):
        k = _close_of(rest, 0)
        rest = rest[k + 1:] if k is not None else rest
    m = re.match(r"\s*([A-Za-z_]\w*)\s*[\[(]", rest)
    return m.group(1) if m else None


def _generic_start(pre):
    """Index of the < that opens the trailing generic args of pre (which ends with >), or -1."""
    depth, k = 0, len(pre.rstrip()) - 1
    while k >= 0:
        depth += pre[k] == ">"; depth -= pre[k] == "<"
        if depth == 0:
            break
        k -= 1
    return k


def _drop_generics(pre):
    """Name<T, U>( -> Name("""
    while pre.rstrip().endswith(">") and "operator" not in pre[-12:]:
        k = _generic_start(pre)
        if k <= 0:
            break
        pre = pre[:k]
    return pre


def _plain_name(h, pre):
    m = re.search(r"((?:[A-Za-z_~$][\w$]*\s*::\s*)*(?:operator\s*\W+|~?[A-Za-z_$][\w$]*))\s*(?:<[^()]*>)?\s*$", pre)
    if not m:
        return None
    name = re.sub(r"\s+", "", m.group(1))
    if name in NOT_NAMES:
        return None
    # what follows the parameter list must look like a function tail, not a call or a declaration with an initializer
    close = _close_of(h, h.index("("))
    tail = h[close + 1:] if close is not None else ""
    return None if re.search(r"^\s*[;,]", tail) else name


def name_of(header, ext=""):
    h = MODS.sub("", header.strip())
    special = _special_name(h, ext)
    if special:
        return special
    h = re.sub(r"\b(template\s*<[^{]*?>)", " ", h).strip()
    if not h or CONTROL.match(h) or "(" not in h:
        return None
    pre = h[:h.index("(")]
    is_value, name = _value_name(pre)
    if is_value:
        return name
    if SCOPE.search(pre) or "=" in re.sub(r"(==|!=|<=|>=|=>|operator\s*\W+)", "", pre):
        return None
    if re.match(r"^func\b", pre):
        return _go_name(h)
    if not _BRK("structure_round3"):
        pre = _drop_generics(pre)
    return _plain_name(h, pre)


class _Reader:
    """Walks the cleaned lines character by character, tracking brackets, the header being read and open blocks."""
    def __init__(self, lines, clean, ext):
        self.lines, self.clean, self.ext = lines, clean, ext
        self.out, self.stack, self.header, self.hstart, self.paren = [], [], [], None, 0
        self.func_open = None                         # (name, start line, stack depth) of the function being read
        self.last_header, self.macro = "", False

    def reset(self):
        self.header, self.hstart = [], None

    def _continues(self, i):
        return self.lines[i].rstrip().endswith("\\") and not _BRK("structure_round3")

    def skip_line(self, i, ln):
        """Preprocessor lines and their continuations. True when the line is skipped."""
        if self.macro:                                # continuation lines of a multi-line #define
            self.macro = self._continues(i)
            return True
        if ln.lstrip().startswith("#") and self.ext != ".py":
            self.macro = self._continues(i)
            if self.paren == 0: self.reset()           # preprocessor lines (#include, #pragma, #define) end any header
            return True
        return False

    def line_ends_statement(self):
        if self.ext not in (".go", ".kt", ".kts", ".swift") or self.paren:
            return False
        return self.ext == ".go" or not _BRK("structure_round3")

    def func_name(self, text):
        nm = name_of(text, self.ext)
        if nm in ("get", "set", "init", "add", "remove") and self.ext == ".cs":
            prop = re.findall(r"[A-Za-z_]\w*", self.last_header)
            nm = (prop[-1] + "." + nm) if prop else nm
        return nm

    def open_block(self, i):
        text = "".join(self.header)
        kind = "other"
        nm = self.func_name(text) if self.func_open is None else None
        if nm:
            start = self.hstart if self.hstart is not None else i
            while start < i and re.match(r"^\s*(@|\[|[A-Z][A-Z0-9_]{2,}\s*\(|$)", self.clean[start]):
                start += 1                            # decorators, attributes, UFUNCTION(...) lines are not the function
            self.func_open = (nm, start, len(self.stack)); kind = "func"
        self.last_header = text
        self.stack.append(kind); self.reset()

    def close_block(self, i):
        if self.stack:
            self.stack.pop()
        if self.func_open and len(self.stack) == self.func_open[2]:
            self.out.append((self.func_open[0], self.func_open[1], i)); self.func_open = None
        self.reset()

    def char(self, i, ch):
        if ch in "([":
            self.paren += 1
        elif ch in ")]":
            self.paren = max(0, self.paren - 1)
        top = self.paren == 0
        if top and ch in "{};":
            {"{": self.open_block, "}": self.close_block, ";": lambda _i: self.reset()}[ch](i)
            return
        if self.hstart is None and not ch.isspace():
            self.hstart = i
        self.header.append(ch)


def functions(lines, ext=""):
    """[(name, start index, end index)] for every outermost function body."""
    clean = clean_lines(lines, ext)
    r = _Reader(lines, clean, ext)
    for i, ln in enumerate(clean):
        if r.skip_line(i, ln):
            continue
        if r.line_ends_statement():
            r.reset()                                 # Go statements end at the line break
        for ch in ln:
            r.char(i, ch)
        r.header.append(" ")
    return r.out, clean
