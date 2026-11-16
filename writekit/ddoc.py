"""Digonto Write's own document file (.ddoc): a small zip that keeps the full DOCX layout plus a manifest."""
import json
import os
import tempfile
import zipfile

from . import docx

MAGIC = "digonto-write"


def write_ddoc(doc, path, page, meta):
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "document.docx")
        docx.write_docx(doc, tmp, page, meta)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps({"app": MAGIC, "format": 1, "content": "document.docx"}))
            z.write(tmp, "document.docx")


def read_ddoc(path):
    with zipfile.ZipFile(path) as z:
        try:
            man = json.loads(z.read("manifest.json"))
        except KeyError:
            raise ValueError("this is not a Digonto Write document")
        if man.get("app") != MAGIC:
            raise ValueError("this is not a Digonto Write document")
        with tempfile.TemporaryDirectory() as td:
            tmp = os.path.join(td, "document.docx")
            with open(tmp, "wb") as f:
                f.write(z.read(man.get("content", "document.docx")))
            return docx.read_docx(tmp)
