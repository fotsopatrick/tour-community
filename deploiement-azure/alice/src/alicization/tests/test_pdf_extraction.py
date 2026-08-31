#!/usr/bin/env python3
# test_pdf_extraction.py
# Prouve que l'ingestion PDF d'ALICE fonctionne SANS pdftotext (poppler-utils),
# via la bibliothèque pure Python `pypdf`, avec fallback pdftotext si présent.
#
# Scénario réel sur ACI (python:3.12-slim, sans poppler) :
#   - on génère un vrai PDF texte avec pypdf ;
#   - on neutralise pdftotext (comme sur le conteneur où il est absent) ;
#   - on extrait via fichier_vers_texte() -> doit rendre le texte, sans erreur.
#
# Usage:
#   python3 -m pytest tests/test_pdf_extraction.py -v
#   python3 -m unittest tests.test_pdf_extraction -v

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from pypdf import PdfWriter
    PYPDF_OK = True
except Exception:
    PYPDF_OK = False

from knowledge import fichier_vers_texte


def _creer_pdf_texte(nom="demo-banque.pdf"):
    """Construit un vrai PDF (couche texte) avec le motif attendu."""
    import pypdf
    from reportlab.pdfgen import canvas  # noqa: F401  (non disponible partout)
    raise NotImplementedError


def _creer_pdf_pypdf(nom="demo-banque.pdf"):
    """PDF minimal contenant une couche texte lisible par pypdf."""
    # Un PDF minimal avec du texte brut exige un ContentStream; plutôt que
    # de dépendre de reportlab, on écrit un petit PDF valide à la main.
    obj = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/"
        b"Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 90>>stream\n"
        b"BT /F1 12 Tf 72 700 Td (RIB ACTIVITE BANCAIRE MONTANT 1234) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"0000000218 00000 n \n0000000340 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\n"
        b"startxref\n401\n%%EOF\n"
    )
    p = Path(tempfile.gettempdir()) / nom
    p.write_bytes(obj)
    return str(p)


@unittest.skipUnless(PYPDF_OK, "pypdf non installé")
class TestExtractionPDFSansPoppler(unittest.TestCase):
    """L'ingestion PDF d'ALICE doit marcher sur un conteneur sans pdftotext."""

    def test_pdf_extrait_sans_pdftotext(self):
        """Le texte d'un PDF est récupéré via pypdf même si pdftotext est absent."""
        chemin = _creer_pdf_pypdf()
        self.addCleanup(os.unlink, chemin)

        # Simule le conteneur ACI : pdftotext introuvable.
        with _sans_pdftotext():
            texte = fichier_vers_texte(chemin)

        self.assertIn("BANCAIRE", texte.upper(),
                      "le texte du PDF doit être extrait par pypdf sans poppler")
        self.assertIn("MONTANT", texte.upper())

    def test_pdf_echoue_sans_module(self):
        """Sans pypdf ni pdftotext, une erreur EXPLICITE est levée (pas de crash silencieux)."""
        import importlib
        import knowledge
        chemin = _creer_pdf_pypdf()
        self.addCleanup(os.unlink, chemin)
        saved = knowledge._PDF_ENGINE
        knowledge._PDF_ENGINE = "none"
        try:
            with self.assertRaises(RuntimeError):
                with _fraude_sys_modules():
                    fichier_vers_texte(chemin)
        finally:
            knowledge._PDF_ENGINE = saved


class _sans_pdftotext:
    """Contexte : pdftotext absent (shutil.which -> None) et pypdf neutralisé
    PAS pour ce test-ci (qui veut justement prouver pypdf)."""
    def __init__(self):
        import shutil
        self._orig = shutil.which
    def __enter__(self):
        import shutil
        def _vide(name, *a, **k):
            if name == "pdftotext":
                return None
            return self._orig(name, *a, **k)
        shutil.which = _vide
    def __exit__(self, *a):
        import shutil
        shutil.which = self._orig


class _fraude_sys_modules:
    """Neutralise pypdf ET pdftotext pour tester le chemin d'erreur explicite."""
    def __init__(self):
        import shutil
        self._o = shutil.which
    def __enter__(self):
        import sys, shutil
        def _vide(name, *a, **k):
            return None if name == "pdftotext" else self._o(name, *a, **k)
        shutil.which = _vide
        self._saved = sys.modules.get("pypdf")
        sys.modules["pypdf"] = None
    def __exit__(self, *a):
        import sys, shutil
        shutil.which = self._o
        if self._saved is not None:
            sys.modules["pypdf"] = self._saved
        else:
            sys.modules.pop("pypdf", None)


if __name__ == "__main__":
    unittest.main()
