# -*- coding: utf-8 -*-
"""Le contrôle de la garde.

Une règle écrite dans une consigne n'est pas suivie ; une règle codée l'est.
Mais une règle codée qu'on ne contrôle pas est une croyance. Ces tests jouent
la vraie bascule : ils demandent l'accès pour de bon, et vérifient que le
refus tombe ET qu'il laisse une trace lisible.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "tour_recherche")
class TestGardeRecherche(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        S = cls.env["recherche.source"]
        cls.ferme = S.create({
            "name": "TEST boîte fermée", "genre": "mail",
            "adresse": "test@exemple.fr", "cercle": "1",
            "pour_quoi": "mes candidatures",
        })
        cls.agents = S.create({
            "name": "TEST endroit des agents", "genre": "web",
            "cercle": "2", "pour_quoi": "des missions",
        })
        cls.invites = S.create({
            "name": "TEST vitrine", "genre": "web",
            "cercle": "4", "pour_quoi": "la démonstration",
        })
        cls.eteint = S.create({
            "name": "TEST endroit éteint", "genre": "web",
            "cercle": "4", "actif": False, "pour_quoi": "la démonstration",
        })

    def _noms(self, cercle, pour_quoi=None):
        sources = self.env["recherche.source"].sources_pour(cercle, pour_quoi)
        return set(sources.filtered(lambda s: s.name.startswith("TEST")).mapped("name"))

    def test_cercle1_voit_tout(self):
        noms = self._noms("1")
        self.assertIn("TEST boîte fermée", noms)
        self.assertIn("TEST endroit des agents", noms)
        self.assertIn("TEST vitrine", noms)

    def test_agents_ne_voient_pas_le_cercle_ferme(self):
        noms = self._noms("2")
        self.assertNotIn("TEST boîte fermée", noms)
        self.assertIn("TEST endroit des agents", noms)
        self.assertIn("TEST vitrine", noms)

    def test_invite_ne_voit_que_le_cercle_4(self):
        noms = self._noms("4")
        self.assertEqual(noms, {"TEST vitrine"})

    def test_eteint_exclu_meme_pour_patrick(self):
        """Décoché veut dire décoché — le cercle fermé n'y va pas non plus."""
        self.assertNotIn("TEST endroit éteint", self._noms("1"))

    def test_pour_quoi_filtre(self):
        noms = self._noms("1", "candidatures")
        self.assertEqual(noms, {"TEST boîte fermée"})

    def test_acces_refuse_leve_une_erreur(self):
        with self.assertRaises(AccessError):
            self.ferme.verifier_acces("2")

    def test_acces_accorde_ne_leve_rien(self):
        self.assertTrue(self.ferme.verifier_acces("1"))

    def test_endroit_eteint_refuse(self):
        with self.assertRaises(AccessError):
            self.eteint.verifier_acces("1")

    def test_un_passage_accepte_laisse_une_trace(self):
        self.ferme.noter_passage("1", "Raphaël", "mes candidatures", trouve=7)
        trace = self.env["recherche.passage"].search(
            [("source_id", "=", self.ferme.id), ("refuse", "=", False)], limit=1)
        self.assertTrue(trace)
        self.assertEqual(trace.trouve, 7)
        self.assertEqual(trace.qui, "Raphaël")

    def test_un_refus_laisse_une_trace(self):
        """Sans cette ligne, un refus est invisible : on le croit, on ne le lit pas."""
        with self.assertRaises(AccessError):
            self.agents.noter_passage("4", "Invité démo", "des missions")
        self.env["recherche.source"].noter_refus(
            self.agents.id, "4", "Invité démo", "des missions",
            "Cercle 2 : un invité n'y entre pas.")
        trace = self.env["recherche.passage"].search(
            [("source_id", "=", self.agents.id), ("refuse", "=", True)], limit=1)
        self.assertTrue(trace)
        self.assertIn("n'y entre pas", trace.note)

    def test_le_compteur_se_lit_dans_le_journal(self):
        """Le compteur n'est pas tenu à la main : il compte les vraies lignes."""
        depart = self.invites.passages_count
        self.invites.noter_passage("4", "Invité démo", "la démonstration", trouve=1)
        self.invites.invalidate_recordset()
        self.assertEqual(self.invites.passages_count, depart + 1)
        self.assertTrue(self.invites.dernier_passage)
