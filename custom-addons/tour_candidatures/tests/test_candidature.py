# -*- coding: utf-8 -*-
"""Le contrôle des candidatures.

Ce qui compte ici n'est pas que les champs existent, mais que le compteur de
silence dise la vérité et qu'une candidature oubliée remonte toute seule. Un
suivi de candidatures qui n'alerte pas est un carnet, pas un outil.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "tour_candidatures")
class TestCandidature(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.C = cls.env["candidature.fiche"]
        cls.aujourdhui = fields.Date.context_today(cls.C)

    def _fiche(self, jours, **kw):
        vals = {"name": "TEST poste", "entreprise": "TEST boite",
                "date_envoi": self.aujourdhui - timedelta(days=jours)}
        vals.update(kw)
        return self.C.create(vals)

    def test_le_silence_se_compte_depuis_l_envoi(self):
        f = self._fiche(12)
        self.assertEqual(f.jours_sans_reponse, 12)

    def test_une_nouvelle_remet_le_compteur_a_zero(self):
        f = self._fiche(30)
        f.derniere_nouvelle = self.aujourdhui - timedelta(days=3)
        self.assertEqual(f.jours_sans_reponse, 3)

    def test_le_bouton_repondu_remet_a_zero(self):
        f = self._fiche(40)
        f.action_noter_nouvelle()
        self.assertEqual(f.jours_sans_reponse, 0)

    def test_une_vivante_oubliee_remonte_toute_seule(self):
        f = self._fiche(15, etat="envoyee")
        self.assertTrue(f.a_relancer)

    def test_une_recente_ne_remonte_pas(self):
        f = self._fiche(3, etat="envoyee")
        self.assertFalse(f.a_relancer)

    def test_une_refusee_ne_remonte_jamais(self):
        """On ne relance pas un refus : ce serait du bruit, donc de l'oubli."""
        f = self._fiche(90, etat="refusee")
        self.assertFalse(f.a_relancer)

    def test_une_arretee_par_moi_ne_remonte_pas(self):
        """Le cas CGI : c'est Patrick qui a ferme. La balle n'est pas chez eux."""
        f = self._fiche(60, etat="arretee")
        self.assertFalse(f.a_relancer)

    def test_le_filtre_a_relancer_est_cherchable(self):
        vieille = self._fiche(20, etat="envoyee", name="TEST vieille")
        self._fiche(2, etat="envoyee", name="TEST fraiche")
        trouvees = self.C.search([("a_relancer", "=", True)])
        self.assertIn(vieille, trouvees)
        self.assertNotIn("TEST fraiche", trouvees.mapped("name"))

    def test_l_ecart_se_lit_jamais_ne_se_saisit(self):
        f = self._fiche(1, remuneration=60000.0, remuneration_proposee=52000.0)
        self.assertEqual(f.ecart, -8000.0)

    def test_toutes_les_portes_existent(self):
        """Salariat, consulting, mission : aucune n'est meilleure, elles existent."""
        portes = dict(self.C._fields["porte"].selection)
        for p in ("salariat", "consulting", "mission"):
            self.assertIn(p, portes)

    def test_preparer_sans_offre_refuse_et_le_dit(self):
        f = self._fiche(1)
        with self.assertRaises(UserError):
            f.action_preparer_entretien()

    def test_preparer_cree_la_fiche_d_entretien(self):
        f = self._fiche(1, offre="On cherche quelqu'un qui sait construire.")
        f.action_preparer_entretien()
        self.assertTrue(f.entretien_id)
        self.assertEqual(f.entretien_id.entreprise, "TEST boite")
        self.assertIn("construire", f.entretien_id.offre)

    def test_preparer_deux_fois_ne_duplique_pas(self):
        f = self._fiche(1, offre="Une offre.")
        f.action_preparer_entretien()
        premier = f.entretien_id
        f.action_preparer_entretien()
        self.assertEqual(f.entretien_id, premier)

    def test_le_resume_compte_les_vraies_fiches(self):
        self._fiche(20, etat="envoyee", name="TEST resume 1")
        self._fiche(1, etat="entretien", name="TEST resume 2")
        self._fiche(50, etat="refusee", name="TEST resume 3")
        r = self.C._resume()
        self.assertGreaterEqual(r["vivantes"], 2)
        self.assertGreaterEqual(r["a_relancer"], 1)
        self.assertGreaterEqual(r["silence_max"], 20)
