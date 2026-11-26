"""FoundationGuard: make the kit's own GitHub App in one click (AI-made, Claude, 2026-11-17; Plan 2 merge B).

Why: spike S3 (15 Nov) showed that a workflow on a change's branch can post a green check with the kit's name. Only a
check posted by the kit's own GitHub App, whose key only main can use, can't be faked that way (S7, S10).

The OWNER runs this on their own computer, signed in to GitHub in their browser as the account that should own the app
(a person, or with --org the organisation):
  python fg/app.py [--org ORG] [--name NAME]
It opens a page on this computer with one button. The button sends GitHub the app's settings (the "manifest"):
  - checks: write          posts the "FoundationGuard note" check
  - pull requests: write   puts the note in the description and asks the right people to review
  - contents: read         reads the change's commits as data
  - metadata: read         always needed
  - no webhook, no events, private (only the account that makes it can install it)
GitHub shows them and asks you to confirm. Then it hands back the app's number and its key. The key is saved in
~/.foundationguard/ (outside every project, readable only by you), and the kit prints the four clicks that remain: install
the app on the project, make the "fg-kit" environment with main as its only branch, add FG_APP_ID and FG_APP_KEY there,
and delete the saved key. Last, tell your helper the app's number; it sets kit_app_id, and python fg/lock.py checks it all.

  python fg/app.py --manifest    print the settings it would send, and change nothing
  --public    let other accounts install it too (needed when the account that makes it, for example the helpers'
              bot, isn't the one that owns the project). Only the key's holder can act as the app, and the key stays
              in the project's fg-kit environment.
"""
import http.server, json, os, secrets, sys, threading, urllib.parse, urllib.request, webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
WAIT = 900


def manifest(name, redirect, public=False):
    perms = {"checks": "write", "pull_requests": "write", "contents": "read", "metadata": "read"}
    if BREAK("app_perms"):
        perms.update(administration="write", secrets="write")
    return {"name": name, "url": "https://github.com", "redirect_url": redirect, "public": bool(public),
            "hook_attributes": {"url": "https://example.invalid/none", "active": False},
            "default_permissions": perms, "default_events": [],
            "description": "Posts the FoundationGuard note check on pull requests. Made with fg/app.py."}


def page(target, man, state):
    """The one-button page: a form that sends the manifest to GitHub."""
    esc = lambda x: x.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return ("<!doctype html><meta charset=utf-8><title>Make the kit's GitHub App</title>"
            "<body style='font:16px system-ui;max-width:40em;margin:3em auto;padding:0 1em'>"
            "<h1>Make the kit's GitHub App</h1><p>This sends GitHub the app's settings. GitHub shows them and asks you to "
            "confirm. It can post checks and notes on pull requests and read the code; it can't change settings or code.</p>"
            f"<form action=\"{esc(target)}?state={esc(state)}\" method=post>"
            f"<input type=hidden name=manifest value=\"{esc(json.dumps(man))}\">"
            "<button style='font-size:1.2em;padding:.6em 1.4em'>Make the app on GitHub</button></form>")


def finish(conv, home):
    """Save what GitHub handed back (the app's number, name and key). Returns the lines for the owner."""
    os.makedirs(home, exist_ok=True)
    key = os.path.join(home, f"{conv.get('slug') or 'fg-app'}.pem")
    fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)      # readable only by the owner from the start
    with os.fdopen(fd, "w") as f:
        f.write(conv.get("pem") or "")
    url = conv.get("html_url") or ""
    return [f"The app is made: {conv.get('name')} (its number is {conv.get('id')}).",
            f"Its key is saved here, readable only by you: {key}",
            "Four clicks remain, in your browser:",
            f"  1. Install it on the project only: {url}/installations/new",
            "  2. Project > Settings > Environments > New environment, named fg-kit. Deployment branches: Selected "
            "branches, add main only.",
            f"  3. In fg-kit: add the variable FG_APP_ID = {conv.get('id')}, and the secret FG_APP_KEY = the whole key "
            "file's text (open it in Notepad and copy everything).",
            "  4. Delete the key file. GitHub keeps the key; you can make a new one on the app's page any time.",
            f"Then tell your helper: the kit's app number is {conv.get('id')}. It sets kit_app_id, and python "
            "fg/lock.py checks all of it."]


def convert(code, opener=urllib.request.urlopen):
    req = urllib.request.Request(f"https://api.github.com/app-manifests/{urllib.parse.quote(code)}/conversions",
                                 method="POST", data=b"", headers={"Accept": "application/vnd.github+json",
                                                                   "User-Agent": "foundationguard"})
    with opener(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv):
    name = argv[argv.index("--name") + 1] if "--name" in argv[:-1] else "foundationguard-" + secrets.token_hex(3)
    org = argv[argv.index("--org") + 1] if "--org" in argv[:-1] else ""
    target = f"https://github.com/organizations/{org}/settings/apps/new" if org else "https://github.com/settings/apps/new"
    if "--manifest" in argv:
        print(json.dumps(manifest(name, "http://127.0.0.1:PORT/done", "--public" in argv), indent=2)); return 0
    state, done = secrets.token_urlsafe(16), {}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            if u.path == "/done" and q.get("state") == [state] and q.get("code"):
                try:
                    done["lines"] = finish(convert(q["code"][0]), os.path.expanduser("~/.foundationguard"))
                    body = "<p>Done. Go back to the window where you ran the kit: it shows the last clicks.</p>"
                except Exception as e:                                   # noqa: BLE001
                    done["lines"] = [f"GitHub didn't hand the app back ({type(e).__name__}). Run python fg/app.py again."]
                    body = "<p>Something went wrong. Go back to the kit's window.</p>"
            elif u.path == "/":
                body = page(target, man, state)
            else:
                self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(body.encode("utf-8"))

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    man = manifest(name, f"http://127.0.0.1:{srv.server_port}/done", "--public" in argv)
    url = f"http://127.0.0.1:{srv.server_port}/"
    print(f"FoundationGuard: open {url} in the browser where you're signed in to GitHub, and press the button.")
    try:
        webbrowser.open(url)
    except Exception:                                                    # noqa: BLE001
        pass
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    for _ in range(WAIT):
        if "lines" in done:
            break
        threading.Event().wait(1)
    srv.shutdown()
    print("\n".join("FoundationGuard: " + l if i == 0 else l for i, l in
                    enumerate(done.get("lines") or ["no answer from GitHub in 15 minutes; nothing was made."])))
    return 0 if "lines" in done else 1


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]):
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
