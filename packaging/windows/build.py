"""Lays out what the Windows download installs (AI-made, Claude, 2026-11-19; beta gate line 4: no Python install).

  python packaging/windows/build.py            makes build/stage/: python/ (python.org's small "embeddable" Python, with
                                               the kit's marker file beside python.exe), fg/, the guides and the licences

The Python is downloaded from python.org and checked against the SHA-256 written below before anything is unpacked.
Inno Setup then turns build/stage/ into build/FoundationGuard-Setup.exe (foundationguard.iss; the "windows-download"
job in .github/workflows/tests.yml does both, installs it with every other Python off the PATH and runs
check_download.py with the installed Python).
"""
import hashlib, io, os, shutil, subprocess, sys, urllib.request, zipfile

PY_VERSION = "3.12.10"
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
PY_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"   # read 19 Nov 2026; its MD5 matched python.org's page
MARK = "foundationguard-python.txt"                 # fg/config.py KIT_PYTHON_MARK
BESIDE = ["AGENT_SETUP.md", "README.md", "LICENSE", "DEPENDENCIES_AND_LICENCES.md", "CHANGELOG.md", "SECURITY.md"]
TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def python_zip(path=None):
    """The embeddable Python's bytes, from a file already here or from python.org; refused unless the sum matches."""
    data = open(path, "rb").read() if path else urllib.request.urlopen(PY_URL, timeout=120).read()
    got = hashlib.sha256(data).hexdigest()
    if got != PY_SHA256:
        raise SystemExit(f"build: the Python download is not the one expected (sha256 {got}); nothing was built")
    return data


def tracked(*paths):
    out = subprocess.run(["git", "ls-files", "-z", "--", *paths], cwd=TOP, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def stage(out, zip_path=None):
    if os.path.exists(out):
        shutil.rmtree(out)
    py = os.path.join(out, "python"); os.makedirs(py)
    zipfile.ZipFile(io.BytesIO(python_zip(zip_path))).extractall(py)
    with open(os.path.join(py, MARK), "w", encoding="utf-8") as f:
        f.write(f"FoundationGuard's own Python ({PY_VERSION}, from python.org, unchanged). The kit's safety checks run on it.\n"
                "Removing this folder stops them in every project set up with it.\n")
    for rel in tracked("fg", "docs", "examples") + BESIDE:
        dest = os.path.join(out, rel); os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(os.path.join(TOP, rel), dest)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    zp = a[a.index("--zip") + 1] if "--zip" in a else None
    print("build: staged in " + stage(os.path.join(TOP, "build", "stage"), zp))
