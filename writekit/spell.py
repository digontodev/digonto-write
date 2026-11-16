"""English spell checker: word list with frequencies (from pyspellchecker's English list, MIT licence) + edit-distance suggestions."""
import gzip
import os
import re

from PySide6.QtCore import QStandardPaths

WORD = re.compile(r"[A-Za-z][A-Za-z'’]*[A-Za-z]|[A-Za-z]")
ALPHA = "abcdefghijklmnopqrstuvwxyz'"


class Speller:
    def __init__(self, lang="en"):
        self.words = {}
        self.loaded = False
        self.lang = lang
        self.ignore = set()
        self.personal = set()
        self.personal_path = None

    def load(self):
        if self.loaded:
            return
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dict", f"{self.lang}.txt.gz")
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    w, _, c = line.rstrip("\n").partition("\t")
                    self.words[w] = int(c or 1)
        except OSError:
            pass
        d = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation) or os.path.expanduser("~")
        self.personal_path = os.path.join(d, "personal-dictionary.txt")
        try:
            with open(self.personal_path, encoding="utf-8") as f:
                self.personal = {l.strip().lower() for l in f if l.strip()}
        except OSError:
            pass
        self.loaded = True

    def add_personal(self, word):
        self.load()
        self.personal.add(word.lower())
        try:
            os.makedirs(os.path.dirname(self.personal_path), exist_ok=True)
            with open(self.personal_path, "a", encoding="utf-8") as f:
                f.write(word.lower() + "\n")
        except OSError:
            pass

    def known(self, w):
        w = w.lower().replace("’", "'")
        if w in self.words or w in self.personal or w in self.ignore:
            return True
        if w.endswith("'s") and (w[:-2] in self.words or w[:-2] in self.personal):
            return True
        if w.endswith("s'") and w[:-1] in self.words:
            return True
        return False

    def is_wrong(self, word, at_start=True):
        """True when the word should be underlined"""
        if len(word) < 2 or not self.words:
            return False
        if word.isupper():                     # acronyms
            return False
        if any(c.isupper() for c in word[1:]):  # camelCase, iPhone ...
            return False
        if word[0].isupper() and not at_start:  # probably a name
            return False
        return not self.known(word)

    def check_text(self, text):
        """[(start, length)] of misspelled words in one paragraph"""
        self.load()
        out = []
        prev_end = 0
        for m in WORD.finditer(text):
            s, e = m.span()
            w = m.group()
            # skip text glued to digits / @ / / (urls, emails, ids)
            before = text[s - 1] if s > 0 else ""
            after = text[e] if e < len(text) else ""
            if before in "@/._-#0123456789" or after in "@/._-0123456789":
                continue
            between = text[prev_end:s]
            at_start = (prev_end == 0 and not text[:s].strip()) or bool(re.search(r"[.!?]\s*$", text[:s].rstrip() + (" " if text[:s] != text[:s].rstrip() else "")))
            if self.is_wrong(w, at_start=at_start or s == 0):
                out.append((s, e - s))
            prev_end = e
        return out

    def edits1(self, w):
        splits = [(w[:i], w[i:]) for i in range(len(w) + 1)]
        deletes = [a + b[1:] for a, b in splits if b]
        transposes = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1]
        replaces = [a + c + b[1:] for a, b in splits if b for c in ALPHA]
        inserts = [a + c + b for a, b in splits for c in ALPHA]
        return set(deletes + transposes + replaces + inserts)

    def suggest(self, word, limit=6):
        self.load()
        w = word.lower().replace("’", "'")
        cand = [c for c in self.edits1(w) if c in self.words]
        if not cand and len(w) > 3:
            for e in self.edits1(w):
                for e2 in self.edits1(e):
                    if e2 in self.words:
                        cand.append(e2)
                if len(cand) > 400:
                    break
        cand = sorted(set(cand), key=lambda c: -self.words.get(c, 0))[:limit]

        def fix(c):
            if word.isupper() and len(word) > 1:
                return c.upper()
            if word[0].isupper():
                return c[:1].upper() + c[1:]
            return c
        return [fix(c) for c in cand]
