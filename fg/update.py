"""FoundationGuard one-step update (AI-made, Claude, 2026-11-17; Plan 2 merge B).

From the project's top folder, run the NEW kit's copy of this file:
  python path/to/new/fg/update.py

It only updates the kit's own code in fg/. The settings, the hooks and the tests are left alone; setup.py does those.
The steps:
  1. When the new kit came with a SHA256SUMS.txt (a transfer folder), every file is checked against it first, and a
     file that doesn't match stops the update before anything changes.
  2. Each file in fg/ is replaced by the new one, a whole file at a time, so a hook running meanwhile reads either the
     old file or the new one.
  3. Each changed file gets a door line, so the check after this step keeps the new kit. That needs the owner: run in
     their own terminal, or by a helper with the owner's yes in the kit's box. Without either, the update stops before
     anything is copied.
  4. Files in fg/ that the new kit doesn't have are listed and left as they are.
This replaces the old copy-then-accept routine (copy fg/*, then steps.py --accept). No --accept is needed afterwards.
"""
import hashlib, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k


def say(x):
    print("FoundationGuard: " + x)


def bad_sums(here):
    """The files of this kit that don't match the SHA256SUMS.txt beside it ([] when there is none, or all match)."""
    sums = os.path.join(os.path.dirname(here), "SHA256SUMS.txt")
    if not os.path.isfile(sums) or BREAK("update_sums"):
        return []
    bad = []
    for line in open(sums, encoding="utf-8", errors="replace"):
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        want, rel = parts[0].lower(), parts[1].lstrip("*").strip()
        p = os.path.join(os.path.dirname(here), rel)
        try:
            data = open(p, "rb").read()
        except OSError:
            bad.append(rel + " (missing)"); continue
        if hashlib.sha256(data).hexdigest() != want and hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() != want:
            bad.append(rel)
    return bad


def owner_first(root, here, dest):
    """The game's PC, 20 Nov: a helper ran the update with no yes from the owner. All 22 files were copied, then the
    check after the step put the 6 guarded ones back, and the kit was half old and half new until the owner ran it
    again. So the owner is checked for before anything is copied: their terminal, or their yes in the kit's box."""
    if BREAK("update_owner_first"):
        return True
    import config as C
    import door as D
    plain = lambda p: open(p, "rb").read().replace(b"\r\n", b"\n")
    same = lambda a, b: os.path.isfile(b) and plain(a) == plain(b)
    names = [n for n in os.listdir(here) if os.path.isfile(os.path.join(here, n)) and not n.endswith(".pyc")]
    differ = [os.path.join(dest, n) for n in names if not same(os.path.join(here, n), os.path.join(dest, n))]
    return D.allowed(C.load(root), differ) == set(differ)


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", stdin=subprocess.DEVNULL).stdout.strip()
    if not top:
        say("run this from your project's top folder (a git folder)."); return 1
    root = os.path.abspath(top)
    dest = os.path.join(root, "fg")
    if os.path.abspath(here) == os.path.abspath(dest):
        say("this is the project's own kit. Run the NEW kit's update.py, for example: python <new kit folder>/fg/update.py"); return 1
    if not os.path.isfile(os.path.join(dest, "guard.py")):
        say("there's no kit in fg/ here yet. To put one in, run setup.py instead."); return 1
    bad = bad_sums(here)
    if bad:
        say("nothing was changed: these files of the new kit don't match its SHA256SUMS.txt, so it may be incomplete or "
            "altered: " + ", ".join(bad[:8]) + ("; and more" if len(bad) > 8 else "") + ". Get the kit again."); return 1
    if not owner_first(root, here, dest):
        say("nothing was changed: updating the kit needs the owner. Either the owner runs this in their own terminal, or "
            "a helper runs this same command as a step of its own and the owner says yes in the kit's box."); return 1
    import setup as S
    S._upgrade(root, here, dest)
    new = {n for n in os.listdir(here) if os.path.isfile(os.path.join(here, n))}
    left = sorted(n for n in os.listdir(dest) if n.endswith(".py") and n not in new)
    if left:
        say("these files in fg/ aren't in the new kit and were left as they are: " + ", ".join(left))
    say("restart any open AI sessions in this project so they use the new kit.")
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
