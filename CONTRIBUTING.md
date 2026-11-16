# Contributing to Digonto Write

Thank you for helping! Digonto Write is part of the [Digonto](https://digonto.dev) programs: free, open source (AGPL-3.0) and fully offline.

## Ground rules

- **Offline, always.** The program must never send the user's files or data anywhere, never "phone home" and never update itself over the internet. Pull requests that add network access for user data are not accepted.
- **Few dependencies.** Prefer the Python standard library and the libraries already in `requirements.txt`. New libraries need a good reason, a pinned version and a SHA-256 hash.
- **Windows, macOS and Linux.** Changes must work on all three (Windows 10/11, macOS 13+, Ubuntu 24.04+ / Debian 13+).
- **Simple English** in the interface, short and clear.
- **No third-party files you may not share**, such as fonts, icons or colour profiles without a licence that allows it.

## Run it from the source

```
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --require-hashes -r requirements.txt
python digonto_write.py
```

## Reporting bugs and ideas

Open an **Issue**: what you did, what you expected, what happened, your system and the version (Help > About).

## Sending a change

1. Fork the repository and make a branch.
2. Keep the change focused: one fix or feature per pull request.
3. Test it on at least one system and say which one in the pull request.
4. **Sign off every commit** (see below), then open a pull request.

## Developer Certificate of Origin (DCO)

By signing off a commit you confirm the [Developer Certificate of Origin 1.1](https://developercertificate.org): you wrote the change, or you have the right to submit it under this project's licence (AGPL-3.0-or-later).

Sign off by adding `-s` when you commit:

```
git commit -s -m "Fix the zoom in the preview"
```

This adds a line with your real name and e-mail:

```
Signed-off-by: Your Name <you@example.com>
```

Forgot it? `git commit --amend -s` fixes the last commit; `git rebase --signoff main` fixes all commits of your branch. A check on every pull request shows if a sign-off is missing.

Your contribution is published under the same licence as the project, AGPL-3.0-or-later.
