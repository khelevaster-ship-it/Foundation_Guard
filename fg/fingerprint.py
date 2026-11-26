"""FoundationGuard setup fingerprint (AI-made, Claude, 2026-11-08).
Records what the machine was running when the gate last passed: OS build, GPU driver, engine version, plugin versions,
Python. If any of them changed, the gate says so and also runs full_gate_command (when set) before trusting the result,
so a sudden failure or slowdown reads as "the driver changed", not as a mystery.
  python fg/fingerprint.py            show the current fingerprint and what changed since the last pass"""
import glob, hashlib, json, os, platform, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20).stdout.strip()
    except Exception:
        return ""


def current(cfg):
    root = cfg["_root"]
    fp = {"os": platform.platform(), "python": platform.python_version()}
    drv = _run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
    if drv:
        fp["gpu_driver"] = drv
    if cfg.get("engine_version_file"):
        p = os.path.join(root, cfg["engine_version_file"])
        fp["engine"] = open(p, encoding="utf-8", errors="replace").read().strip()[:400] if os.path.exists(p) else "MISSING"
    for g in cfg.get("plugin_globs") or []:
        for p in sorted(glob.glob(os.path.join(root, g))):
            fp["plugin:" + os.path.relpath(p, root).replace("\\", "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]
    if os.environ.get("FG_FAKE_DRIVER"):
        fp["gpu_driver"] = os.environ["FG_FAKE_DRIVER"]          # lets the kit's own test change the setup
    return fp


def path(cfg):
    return os.path.join(cfg["_root"], cfg["state_dir"], "fingerprint.json")


def changes(cfg):
    now = current(cfg)
    if not os.path.exists(path(cfg)):
        return now, []
    old = json.load(open(path(cfg), encoding="utf-8-sig"))
    if os.environ.get("FG_BREAK") == "fingerprint":
        return now, []
    return now, [f"{k}: {old.get(k, '(none)')} -> {now.get(k, '(gone)')}" for k in sorted(set(old) | set(now)) if old.get(k) != now.get(k)]


def save(cfg, fp):
    os.makedirs(os.path.dirname(path(cfg)), exist_ok=True); json.dump(fp, open(path(cfg), "w"), indent=1)


if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    cfg = C.load(); now, ch = changes(cfg)
    print(json.dumps(now, indent=1)); print("CHANGED since last pass:\n  " + "\n  ".join(ch) if ch else "No change since last pass.")
