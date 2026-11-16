"""Build standalone Digonto packages (no Python, no internet needed by the user).

    python build.py --root .. --apps digonto-qr                  one program  -> Digonto QR (.deb / .dmg / .exe)
    python build.py --root .. --apps all --package digonto-studio  Studio with every program in it

Run it on the system you build for (GitHub Actions does Linux, macOS and Windows).
The build Python must already have the programs' requirements installed (see --print-requirements).
"""
import argparse
import ast
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = platform.system()
PUBLISHER = "Digonto"
HOMEPAGE = "https://digonto.dev"
# apt packages every Qt program needs on Debian / Ubuntu (the libraries themselves are inside the package)
DEB_BASE = ["libxcb-cursor0", "libxkbcommon-x11-0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1",
            "libxcb-randr0", "libxcb-render-util0", "libxcb-shape0", "libxcb-xinerama0", "libegl1", "libgl1",
            "libfontconfig1", "libdbus-1-3"]


def load_apps(root):
    apps = {}
    for d in sorted(os.listdir(root)):
        f = os.path.join(root, d, "digonto-app.json")
        if os.path.isfile(f):
            with open(f, encoding="utf-8") as fh:
                c = json.load(fh)
            c["_src"] = os.path.join(root, d)
            apps[c["slug"]] = c
    return apps


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


# ---------------------------------------------------------------- stage the programs
def stage(apps, slugs, dst):
    shutil.rmtree(dst, ignore_errors=True)
    for s in slugs:
        c = apps[s]
        out = os.path.join(dst, s)
        os.makedirs(out)
        for item in c["files"] + ["digonto-app.json"]:
            src = os.path.join(c["_src"], item)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(out, item), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif os.path.isfile(src):
                shutil.copy2(src, os.path.join(out, item))
            else:
                raise SystemExit(f"{s}: missing file {item}")


def scan_imports(staged):
    """every module the programs import, minus their own modules -> PyInstaller must collect these"""
    local, found = set(), set()
    for slug in os.listdir(staged):
        d = os.path.join(staged, slug)
        for n in os.listdir(d):
            local.add(n[:-3] if n.endswith(".py") else n)
    for dirpath, _dirs, files in os.walk(staged):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            try:
                tree = ast.parse(open(os.path.join(dirpath, fn), encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        found.add(a.name)
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    found.add(node.module)
                    for a in node.names:
                        if a.name != "*":
                            found.add(node.module + "." + a.name)
    out = sorted(m for m in found if m.split(".")[0] not in local and not m.startswith("_"))
    return out


def write_deps(mods, path):
    lines = ["# generated: the libraries the bundled programs use (each import may be missing on some systems)"]
    for m in mods:
        lines.append(f"try:\n    import {m}  # noqa\nexcept Exception:\n    pass")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------- freeze
def icon_file(app, ext):
    for cand in (f"{app['slug']}.{ext}", f"icon.{ext}"):
        p = os.path.join(app["_src"], "assets", cand)
        if os.path.isfile(p):
            return p
    return None


def freeze(apps, slugs, pkg, work):
    main = apps[pkg]
    staged = os.path.join(work, "apps")
    stage(apps, slugs, staged)
    with open(os.path.join(work, "default-app.txt"), "w") as f:
        f.write(pkg)
    write_deps(scan_imports(staged), os.path.join(work, "_digonto_deps.py"))
    shutil.copy2(os.path.join(HERE, "launcher.py"), os.path.join(work, "launcher.py"))
    name = main["name"] if SYS == "Darwin" else main["slug"]
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
           "--name", name, "--distpath", os.path.join(work, "dist"), "--workpath", os.path.join(work, "pyi"),
           "--specpath", work, "--paths", work,
           "--add-data", f"{staged}{sep}apps", "--add-data", f"{os.path.join(work, 'default-app.txt')}{sep}.",
           "--hidden-import", "_digonto_deps"]
    needs_tk = any(apps[s].get("needs_tk") for s in slugs)
    if not needs_tk:
        cmd += ["--exclude-module", "tkinter"]
    ico = icon_file(main, "ico" if SYS == "Windows" else "icns" if SYS == "Darwin" else "png")
    if ico:
        cmd += ["--icon", ico]
    if SYS == "Darwin":
        cmd += ["--osx-bundle-identifier", "dev.digonto." + main["slug"].replace("digonto-", "")]
    cmd.append(os.path.join(work, "launcher.py"))
    run(cmd, cwd=work)
    out = os.path.join(work, "dist", name + (".app" if SYS == "Darwin" else ""))
    if not os.path.exists(out):
        raise SystemExit("PyInstaller made nothing")
    return out


# ---------------------------------------------------------------- Linux .deb
def build_deb(apps, slugs, pkg, frozen, outdir):
    main = apps[pkg]
    ver = main["version"]
    root = os.path.join(os.path.dirname(frozen), "debroot")
    shutil.rmtree(root, ignore_errors=True)
    opt = os.path.join(root, "opt", "digonto", pkg)
    shutil.copytree(frozen, opt, symlinks=True)
    exe = f"/opt/digonto/{pkg}/{pkg}"
    os.makedirs(os.path.join(root, "usr", "bin"))
    mimes = []
    for s in slugs:
        a = apps[s]
        launcher = os.path.join(root, "usr", "bin", s)
        arg = "" if s == pkg else f" --app {s}"
        with open(launcher, "w") as f:
            f.write(f'#!/bin/sh\nexec {exe}{arg} "$@"\n')
        os.chmod(launcher, 0o755)
        apps_dir = os.path.join(root, "usr", "share", "applications")
        os.makedirs(apps_dir, exist_ok=True)
        mt = list(a.get("mime") or [])
        mimes += [(m, e) for m in mt for e in a.get("extensions", []) if m.startswith("application/x-digonto")]
        with open(os.path.join(apps_dir, f"{s}.desktop"), "w") as f:
            f.write(textwrap.dedent(f"""\
                [Desktop Entry]
                Type=Application
                Name={a['name']}
                Comment={a.get('comment', '')}
                Exec=/usr/bin/{s} %F
                Icon={s}
                Terminal=false
                Categories={a.get('categories', 'Utility;')}
                Keywords={a.get('keywords', '')}
                StartupWMClass={a.get('wm_class', s)}
                MimeType={';'.join(mt) + (';' if mt else '')}
                """))
        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            src = os.path.join(a["_src"], "assets", f"{s}-{size}.png")
            if not os.path.isfile(src):
                src = os.path.join(a["_src"], "assets", f"{s}.png") if size == 256 else None
            if src and os.path.isfile(src):
                d = os.path.join(root, "usr", "share", "icons", "hicolor", f"{size}x{size}", "apps")
                os.makedirs(d, exist_ok=True)
                shutil.copy2(src, os.path.join(d, f"{s}.png"))
    if mimes:
        d = os.path.join(root, "usr", "share", "mime", "packages")
        os.makedirs(d)
        with open(os.path.join(d, f"{pkg}.xml"), "w") as f:
            f.write('<?xml version="1.0"?>\n<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n')
            seen = set()
            for m, e in mimes:
                if m in seen:
                    continue
                seen.add(m)
                globs = "".join(f'<glob pattern="*{x}"/>' for mm, x in mimes if mm == m)
                f.write(f'  <mime-type type="{m}"><comment>{m.split("x-")[-1]} file</comment>{globs}</mime-type>\n')
            f.write("</mime-info>\n")
    deps = list(DEB_BASE)
    for s in slugs:
        deps += [p for p in apps[s].get("apt", []) if p not in deps]
    size_kb = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _d, fs in os.walk(root) for fn in fs
                  if not os.path.islink(os.path.join(dp, fn))) // 1024
    deb = os.path.join(root, "DEBIAN")
    os.makedirs(deb)
    desc = main.get("comment", main["name"])
    with open(os.path.join(deb, "control"), "w") as f:
        f.write(textwrap.dedent(f"""\
            Package: {pkg}
            Version: {ver}
            Section: graphics
            Priority: optional
            Architecture: {'arm64' if platform.machine() in ('aarch64', 'arm64') else 'amd64'}
            Maintainer: Digonto <digontodev@users.noreply.github.com>
            Homepage: {HOMEPAGE}
            Installed-Size: {size_kb}
            Depends: {', '.join(sorted(set(deps)))}
            Description: {main['name']} - {desc}
             Part of the Digonto programs (digonto.dev). Works without internet.
            """))
    for name, body in (("postinst", "update-desktop-database -q /usr/share/applications 2>/dev/null || true\n"
                                    "update-mime-database /usr/share/mime 2>/dev/null || true\n"
                                    "gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true\n"),
                       ("postrm", "update-desktop-database -q /usr/share/applications 2>/dev/null || true\n"
                                  "update-mime-database /usr/share/mime 2>/dev/null || true\n")):
        p = os.path.join(deb, name)
        with open(p, "w") as f:
            f.write("#!/bin/sh\nset -e\n" + body)
        os.chmod(p, 0o755)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{pkg}_{ver}_{'arm64' if platform.machine() in ('aarch64', 'arm64') else 'amd64'}.deb")
    run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", root, out])
    return out


# ---------------------------------------------------------------- macOS .app + .dmg
def build_dmg(apps, slugs, pkg, frozen, outdir):
    main = apps[pkg]
    plist_path = os.path.join(frozen, "Contents", "Info.plist")
    with open(plist_path, "rb") as f:
        pl = plistlib.load(f)
    pl.update({"CFBundleName": main["name"], "CFBundleDisplayName": main["name"],
               "CFBundleShortVersionString": main["version"], "CFBundleVersion": main["version"],
               "LSMinimumSystemVersion": str(main.get("macos_min", 11)), "NSHighResolutionCapable": True,
               "NSHumanReadableCopyright": "Digonto - digonto.dev - AGPL-3.0"})
    docs, utis = [], []
    for s in slugs if len(slugs) == 1 else [pkg]:
        a = apps[s]
        exts = [e.lstrip(".") for e in a.get("extensions", [])]
        if exts:
            docs.append({"CFBundleTypeName": a["name"] + " file", "CFBundleTypeRole": "Editor",
                         "CFBundleTypeExtensions": exts, "LSHandlerRank": "Default",
                         "LSItemContentTypes": a.get("uti", [])})
            for u in a.get("uti", []):
                utis.append({"UTTypeIdentifier": u, "UTTypeDescription": a["name"] + " file",
                             "UTTypeConformsTo": ["public.data"], "UTTypeTagSpecification": {"public.filename-extension": exts}})
    if docs:
        pl["CFBundleDocumentTypes"] = docs
    if utis:
        pl["UTExportedTypeDeclarations"] = utis
    with open(plist_path, "wb") as f:
        plistlib.dump(pl, f)
    # ad-hoc signature, so Apple silicon Macs start it (users still confirm once: right-click > Open)
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", frozen], check=False)
    stage_dir = os.path.join(os.path.dirname(frozen), "dmgroot")
    shutil.rmtree(stage_dir, ignore_errors=True)
    os.makedirs(stage_dir)
    shutil.copytree(frozen, os.path.join(stage_dir, os.path.basename(frozen)), symlinks=True)
    os.symlink("/Applications", os.path.join(stage_dir, "Applications"))
    with open(os.path.join(stage_dir, "READ ME FIRST.txt"), "w") as f:
        f.write(f"Drag {main['name']} into Applications.\n\nThe first time: right-click the program in Applications and "
                "choose Open, then Open again.\nmacOS asks this once because the program is not from the App Store.\n")
    os.makedirs(outdir, exist_ok=True)
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    out = os.path.join(outdir, f"{main['name'].replace(' ', '-')}-{main['version']}-macOS-{arch}.dmg")
    if os.path.exists(out):
        os.remove(out)
    run(["hdiutil", "create", "-volname", main["name"], "-srcfolder", stage_dir, "-ov", "-format", "UDZO", out])
    return out


# ---------------------------------------------------------------- Windows .exe (Inno Setup)
def build_exe(apps, slugs, pkg, frozen, outdir):
    main = apps[pkg]
    exe = f"{pkg}.exe"
    iss = os.path.join(os.path.dirname(frozen), f"{pkg}.iss")
    ico = icon_file(main, "ico")
    lines = [
        "[Setup]",
        f"AppId={{{{Digonto-{pkg}}}}}",
        f"AppName={main['name']}",
        f"AppVersion={main['version']}",
        f"AppPublisher={PUBLISHER}",
        f"AppPublisherURL={HOMEPAGE}",
        f"DefaultDirName={{localappdata}}\\Programs\\Digonto\\{main['name']}",
        "DefaultGroupName=Digonto",
        "DisableProgramGroupPage=yes",
        "PrivilegesRequired=lowest",
        "ChangesAssociations=yes",
        "ArchitecturesInstallIn64BitMode=x64compatible",
        "ArchitecturesAllowed=x64compatible",
        f"OutputDir={outdir}",
        f"OutputBaseFilename={main['name'].replace(' ', '-')}-{main['version']}-Windows-Setup",
        "Compression=lzma2/max",
        "SolidCompression=yes",
        "WizardStyle=modern",
        f"UninstallDisplayIcon={{app}}\\{exe}",
        f"LicenseFile={os.path.join(HERE, 'LICENSE.txt')}",
    ]
    if ico:
        lines.append(f"SetupIconFile={ico}")
    lines += ["", "[Tasks]", 'Name: "desktopicon"; Description: "Make shortcuts on the desktop"; GroupDescription: "Shortcuts:"',
              "", "[Files]", f'Source: "{frozen}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs', "",
              "[Icons]"]
    reg = []
    for s in slugs:
        a = apps[s]
        args = "" if s == pkg else f'; Parameters: "--app {s}"'
        icon = f'; IconFilename: "{{app}}\\_internal\\apps\\{s}\\assets\\{s}.ico"' if icon_file(a, "ico") else ""
        lines.append(f'Name: "{{group}}\\{a["name"]}"; Filename: "{{app}}\\{exe}"{args}{icon}')
        lines.append(f'Name: "{{autodesktop}}\\{a["name"]}"; Filename: "{{app}}\\{exe}"{args}{icon}; Tasks: desktopicon')
        cmdline = (f'"{{app}}\\{exe}" ' + ("" if s == pkg else f"--app {s} ") + '""%1""')
        for e in a.get("extensions", []):
            prog = f"Digonto.{s}{e}"
            reg += [f'Root: HKCU; Subkey: "Software\\Classes\\{e}"; ValueType: string; ValueName: ""; ValueData: "{prog}"; Flags: uninsdeletevalue',
                    f'Root: HKCU; Subkey: "Software\\Classes\\{prog}"; ValueType: string; ValueName: ""; ValueData: "{a["name"]} file"; Flags: uninsdeletekey',
                    f'Root: HKCU; Subkey: "Software\\Classes\\{prog}\\shell\\open\\command"; ValueType: string; ValueName: ""; ValueData: "{cmdline}"']
    lines.append(f'Name: "{{group}}\\Uninstall {main["name"]}"; Filename: "{{uninstallexe}}"')
    if reg:
        lines += ["", "[Registry]"] + reg
    lines += ["", "[Run]", f'Filename: "{{app}}\\{exe}"; Description: "Open {main["name"]}"; Flags: nowait postinstall skipifsilent']
    with open(iss, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    os.makedirs(outdir, exist_ok=True)
    run([iscc, iss])
    return os.path.join(outdir, f"{main['name'].replace(' ', '-')}-{main['version']}-Windows-Setup.exe")


# ---------------------------------------------------------------- main
def requirements_for(apps, slugs):
    return [os.path.join(apps[s]["_src"], apps[s]["requirements"]) for s in slugs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(HERE), help="folder with the digonto-* program folders")
    ap.add_argument("--apps", required=True, help="slugs separated by commas, or 'all'")
    ap.add_argument("--package", help="the program the package is named after (default: the first)")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--print-requirements", action="store_true")
    ap.add_argument("--freeze-only", action="store_true")
    a = ap.parse_args()
    apps = load_apps(os.path.abspath(a.root))
    slugs = sorted(apps) if a.apps == "all" else [s.strip() for s in a.apps.split(",")]
    for s in slugs:
        if s not in apps:
            raise SystemExit(f"unknown program {s}; have: {', '.join(apps)}")
    pkg = a.package or slugs[0]
    if pkg not in slugs:
        slugs.insert(0, pkg)
    if a.print_requirements:
        print("\n".join(requirements_for(apps, slugs)))
        return
    work = os.path.join(os.path.abspath(a.work), pkg)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    frozen = freeze(apps, slugs, pkg, work)
    if a.freeze_only:
        print(frozen)
        return
    out = os.path.abspath(a.out)
    made = {"Linux": build_deb, "Darwin": build_dmg, "Windows": build_exe}[SYS](apps, slugs, pkg, frozen, out)
    print("MADE", made)


if __name__ == "__main__":
    main()
