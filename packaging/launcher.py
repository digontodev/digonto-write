"""Digonto standalone launcher.

One frozen Python + Qt runtime that can start any Digonto program shipped inside it:
    digonto --app digonto-qr [files...]     start one program
    digonto some_script.py [args...]        run a helper script of a program (DTFRIP keep-alive)
    digonto [files...]                      start the default program of this package
The programs are kept as normal source folders in  <bundle>/apps/<slug>/  so they find their own files.
"""
import json
import os
import runpy
import sys

if getattr(sys, "frozen", False):
    BASE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
APPS = os.path.join(BASE, "apps")
os.environ["DIGONTO_STANDALONE"] = "1"
os.environ["DIGONTO_LAUNCHER"] = sys.executable


def user_base():
    """shared data of the Digonto programs (recent files ...): the program folder itself is read-only"""
    if sys.platform == "win32":
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Digonto")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Digonto")
    return os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "digonto")


os.environ.setdefault("DIGONTO_BASE", user_base())


def default_app():
    try:
        with open(os.path.join(BASE, "default-app.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        names = sorted(os.listdir(APPS)) if os.path.isdir(APPS) else []
        return names[0] if names else ""


def run_app(slug, args):
    d = os.path.join(APPS, slug)
    with open(os.path.join(d, "digonto-app.json"), encoding="utf-8") as f:
        conf = json.load(f)
    entry = os.path.join(d, conf["entry"])
    sys.path.insert(0, d)
    sys.argv = [entry] + list(args)
    runpy.run_path(entry, run_name="__main__")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--app" and len(args) >= 2:
        return run_app(args[1], args[2:])
    if args and args[0].endswith(".py") and os.path.isfile(args[0]):
        script = os.path.abspath(args[0])
        sys.path.insert(0, os.path.dirname(script))
        sys.argv = [script] + args[1:]
        return runpy.run_path(script, run_name="__main__")
    if args and args[0] in ("-m", "-c"):            # not a Python: a frozen program cannot run pip or code
        sys.stderr.write("Digonto standalone edition: running Python commands is not possible here.\n")
        sys.exit(2)
    if args and args[0] == "--list":
        print("\n".join(sorted(os.listdir(APPS))))
        return
    return run_app(default_app(), args)


if os.environ.get("DIGONTO_NEVER_SET_THIS"):      # never runs: tells PyInstaller which libraries the programs use
    import _digonto_deps  # noqa: F401

if __name__ == "__main__":
    main()
