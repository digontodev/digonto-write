# Digonto Write

Word processor: DOCX, ODT, HTML, Markdown, PDF

This program is also inside [Digonto Studio](https://github.com/digontodev/digonto-studio), the download with every Digonto program.

Part of the **Digonto** programs - [digonto.dev](https://digonto.dev). Works completely offline: no account, no internet, no tracking.

## Download

Get the newest version from the **[Releases page](https://github.com/digontodev/digonto-write/releases/latest)**:

| System | File |
|---|---|
| Windows 10 / 11 (64-bit) | `Digonto-Write-<version>-Windows-Setup.exe` |
| macOS 13 or newer (Intel and Apple silicon) | `Digonto-Write-<version>-macOS-x86_64.dmg` |
| Ubuntu 24.04+ / Debian 13+ (64-bit) | `digonto-write_<version>_amd64.deb` |

- **Windows:** run the setup file. Windows may show "Windows protected your PC": click *More info* > *Run anyway* (the program is not signed yet).
- **macOS:** open the .dmg and drag the program into Applications, then open it. The first time, macOS says it cannot verify the program (it is not signed with an Apple developer account yet): open **System Settings > Privacy & Security**, scroll down and click **Open Anyway**, then open the program again. This is needed only once. On Macs with an M chip, click *Install* if macOS asks to install Rosetta.
- **Ubuntu / Debian:** `sudo apt install ./digonto-write_<version>_amd64.deb`

## Build it yourself

The installers are made by GitHub Actions (`.github/workflows/release.yml`) on Linux, macOS and Windows.
To build on your own computer: install the libraries in `requirements.txt` and PyInstaller, then run
`python packaging/build.py --root .. --apps digonto-write`.

To run from source: `pip install --require-hashes -r requirements.txt` then `python digonto_write.py`.

## Licence

GNU Affero General Public License v3.0 or later - see [LICENSE](LICENSE). Copyright (C) Digonto.
