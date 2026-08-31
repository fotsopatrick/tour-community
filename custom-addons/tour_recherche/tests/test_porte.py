# -*- coding: utf-8 -*-
"""Le contrôle de la porte : la page ne doit pas contourner la garde.

Une garde en Python ne vaut rien si la porte HTTP rend tout à tout le monde.
Ces tests appellent la porte POUR DE VRAI, avec de vrais comptes de cercles
différents, et vérifient ce qui sort.
"""
import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "tour_recherche")
class TestPorteRecherche(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"]
        cls.groupe1 = cls.env.ref("tour_recherche.group_recherche_cercle1")
        cls.groupe2 = cls.env.ref("tour_recherche.group_recherche_cercle2")
        base_user = cls.env.ref("base.group_user")

        cls.agent = Users.create({
            "name": "Agent de test", "login": "agent_test_recherche",
            "password": "agent_test_recherche",
            "groups_id": [(6, 0, [base_user.id, cls.groupe2.id])],
        })
        cls.invite = Users.create({
            "name": "Invité de test", "login": "invite_test_recherche",
            "password": "invite_test_recherche",
            "groups_id": [(6, 0, [base_user.id])],
        })

    def _lire(self, login, chemin="/api/recherche/endroits"):
        self.authenticate(login, login)
        r = self.url_open(chemin)
        self.assertEqual(r.status_code, 200)
        return json.loads(r.content)

    def test_la_porte_rend_le_cercle_lu_dans_les_groupes(self):
        self.assertEqual(self._lire("agent_test_recherche")["cercle"], "2")
        self.assertEqual(self._lire("invite_test_recherche")["cercle"], "4")

    def test_un_agent_ne_recoit_pas_la_boite_mail(self):
        """Le vrai risque : la page contourne la garde. Elle ne doit pas."""
        noms = [e["nom"] for e in self._lire("agent_test_recherche")["endroits"]]
        self.assertNotIn("La boîte mail de Patrick", noms)
        self.assertIn("La veille de missions", noms)

    def test_un_invite_ne_recoit_que_le_cercle_4(self):
        d = self._lire("invite_test_recherche")
        self.assertTrue(d["endroits"])
        self.assertTrue(all(e["cercle"] == "4" for e in d["endroits"]))

    def test_l_adresse_du_mail_ne_fuit_pas(self):
        """Même l'adresse ne doit pas sortir : c'est déjà une information."""
        brut = json.dumps(self._lire("agent_test_recherche"), ensure_ascii=False)
        self.assertNotIn("fotsoorel95", brut)

    def test_un_agent_ne_peut_pas_toucher_les_interrupteurs(self):
        self.authenticate("agent_test_recherche", "agent_test_recherche")
        veille = self.env.ref("tour_recherche.source_veille_missions")
        avant = veille.actif
        r = self.url_open(
            "/api/recherche/basculer",
            data=json.dumps({"id": veille.id}),
            headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 403)
        veille.invalidate_recordset()
        self.assertEqual(veille.actif, avant, "l'interrupteur a bougé quand même")

    def test_sans_connexion_la_porte_est_fermee(self):
        r = self.url_open("/api/recherche/endroits", allow_redirects=False)
        self.assertNotEqual(r.status_code, 200)

    def test_la_page_s_ouvre(self):
        self.authenticate("agent_test_recherche", "agent_test_recherche")
        r = self.url_open("/ou-chercher")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Où chercher", r.content.decode())
