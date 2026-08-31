# -*- coding: utf-8 -*-
"""Le contrôle « mérite attention » : une ligne du tableau des robots doit
dire, d'un coup d'œil, si elle demande qu'on la regarde.

Écrit AVANT la méthode `_attention` (règle du retest : le contrôle qui trouve
le défaut existe avant le correctif). Le test échoue tant que la méthode
n'existe pas ; il passe quand elle dit ce qu'elle doit dire.

Ce qu'on décide :
- techniques d'attaque reconnues        -> HAUTE (on regarde maintenant) ;
- fouilleur qui a reçu des réponses à poids différents -> HAUTE (fuite possible) ;
- fouilleur / scanner, le reste         -> MOYENNE (surveiller) ;
- humain / moteur normal                -> rien.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.tour_robots.controllers.robots import TourRobots


@tagged("post_install", "-at_install", "tour_robots")
class TestAttention(TransactionCase):

    def test_fouilleur_reponses_differentes_haute(self):
        """Des réponses « oui » de poids différents : une fuite possible."""
        a = self.env["tour.robot.passage"]._attention(
            "fouilleur", fouille=10, fouille_200=3, meme_poids=False)
        self.assertEqual(a, "haute")

    def test_fouilleur_page_passe_partout_moyenne(self):
        """Des réponses « oui » toutes de même poids : rien n'est sorti."""
        a = self.env["tour.robot.passage"]._attention(
            "fouilleur", fouille=10, fouille_200=3, meme_poids=True)
        self.assertEqual(a, "moyenne")

    def test_fouilleur_rien_obtenu_moyenne(self):
        """Le fouilleur n'a reçu que des refus : à surveiller, rien de grave."""
        a = self.env["tour.robot.passage"]._attention(
            "fouilleur", fouille=10, fouille_200=0)
        self.assertEqual(a, "moyenne")

    def test_techniques_dattaque_haute(self):
        """Une technique d'attaque reconnue fait toujours passer en haute."""
        a = self.env["tour.robot.passage"]._attention(
            "moteur", techniques=["injection SQL"])
        self.assertEqual(a, "haute")

    def test_humain_normal_rien(self):
        a = self.env["tour.robot.passage"]._attention("humain")
        self.assertEqual(a, "")

    def test_moteur_normal_rien(self):
        a = self.env["tour.robot.passage"]._attention("moteur")
        self.assertEqual(a, "")

    def test_scanner_sans_reponse_moyenne(self):
        a = self.env["tour.robot.passage"]._attention("scanner")
        self.assertEqual(a, "moyenne")


@tagged("post_install", "-at_install", "tour_robots")
class TestAObtenu(TransactionCase):
    """La colonne « A obtenu » : le fouilleur a-t-il récupéré quelque chose ?

    Oui seulement quand les réponses « oui » ont des poids différents (une
    vraie page a pu partir). La page passe-partout (même poids) ne compte pas :
    le fouilleur a reçu la page d'accueil, pas le fichier demandé.
    """

    def test_reponses_differentes_oui(self):
        a = self.env["tour.robot.passage"]._a_obtenu(
            "fouilleur", fouille_200=3, meme_poids=False)
        self.assertEqual(a, "oui")

    def test_page_passe_partout_non(self):
        a = self.env["tour.robot.passage"]._a_obtenu(
            "fouilleur", fouille_200=3, meme_poids=True)
        self.assertEqual(a, "non")

    def test_rien_obtenu_non(self):
        a = self.env["tour.robot.passage"]._a_obtenu(
            "fouilleur", fouille_200=0)
        self.assertEqual(a, "non")

    def test_non_fouilleur_pas_applicable(self):
        a = self.env["tour.robot.passage"]._a_obtenu("moteur")
        self.assertEqual(a, "")


@tagged("post_install", "-at_install", "tour_robots")
class TestFiltreAObtenu(TransactionCase):
    """Le filtre « A obtenu » (cliquer la colonne) ne rend que les lignes qui
    correspondent : 'oui' (réponses à poids différents), 'non' (rien de
    sensible), '' (tout). Écrit AVANT la méthode de filtrage.
    """

    def setUp(self):
        super().setUp()
        P = self.env["tour.robot.passage"]
        self.fouilleur_oui = P.create({
            "jour": "2026-08-20", "robot": "TestA", "site": "test.matourdecontrole.fr",
            "categorie": "fouilleur", "fouille": 3, "fouille_200": 2,
            "pages_200": '[["/.env|631", 1]]',
        })
        self.fouilleur_non = P.create({
            "jour": "2026-08-20", "robot": "TestB", "site": "test.matourdecontrole.fr",
            "categorie": "fouilleur", "fouille": 3, "fouille_200": 2,
            "pages_200": '[["/a|490", 1], ["/b|490", 1]]',
        })
        self.moteur = P.create({
            "jour": "2026-08-20", "robot": "TestC", "site": "test.matourdecontrole.fr",
            "categorie": "moteur",
        })

    def test_filtre_oui(self):
        ctl = TourRobots()
        r = ctl._filtrer_a_obtenu(
            self.env["tour.robot.passage"].search([("robot", "like", "Test%")]),
            "oui")
        self.assertEqual(list(r.ids), [self.fouilleur_oui.id])

    def test_filtre_non(self):
        ctl = TourRobots()
        r = ctl._filtrer_a_obtenu(
            self.env["tour.robot.passage"].search([("robot", "like", "Test%")]),
            "non")
        self.assertIn(self.fouilleur_non.id, r.ids)
        self.assertNotIn(self.fouilleur_oui.id, r.ids)
        self.assertNotIn(self.moteur.id, r.ids)

    def test_filtre_vide_rend_tout(self):
        ctl = TourRobots()
        r = ctl._filtrer_a_obtenu(
            self.env["tour.robot.passage"].search([("robot", "like", "Test%")]),
            "")
        self.assertEqual(len(r.ids), 3)
