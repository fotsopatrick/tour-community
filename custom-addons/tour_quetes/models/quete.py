# -*- coding: utf-8 -*-
"""Quêtes de carrière — une offre d'emploi devient un registre de quêtes.

Principe QuestForge porté dans la tour : on ne recopie pas l'application
(React + Supabase), on reprend son geste — une offre collée devient un
ensemble de quêtes. Ici, la règle est de COUVRIR TOUTES les compétences de
l'annonce : chaque skill détectée reçoit sa quête « Maîtrise — X », aucune
n'est laissée de côté. L'extraction est déterministe (un lexique), donc
reproductible et testable — pas une opinion de session.

L'XP reste honnête (garde-fou tour_equipage) : un compteur « quêtes de
carrière » MESURE les quêtes terminées, et la relève consigne chaque gain
dans `equipe.exploit`. Jamais de point posé à la main.
"""
import re

from odoo import _, api, fields, models

# ---------------------------------------------------------------------------
# Le lexique des compétences. La clé est un motif (regex), la valeur le nom
# canonique de la skill. On balaye TOUT le texte de l'offre : chaque skill
# trouvée devient une quête. L'ordre du lexique compte peu ; on évite les
# faux positifs en exigeant un mot entier (\b) et en mettant les expressions
# composées avant leurs mots simples.
# ---------------------------------------------------------------------------
SKILL_LEXIQUE = [
    (r"\bpython\b", "Python"),
    (r"\bwordpress\b", "WordPress"),
    (r"\bsql\b", "SQL"),
    (r"\bpostgres(ql)?\b", "PostgreSQL"),
    (r"\bflask\b", "Flask"),
    (r"\bdjango\b", "Django"),
    (r"\btypescript\b", "TypeScript"),
    (r"\bjavascript\b", "JavaScript"),
    (r"\breact( native)?\b", "React"),
    (r"\bvue(\.js)?\b", "Vue.js"),
    (r"\bnode(\.js)?\b", "Node.js"),
    (r"\bphp\b", "PHP"),
    (r"\bsymfony\b", "Symfony"),
    (r"\bflutter\b", "Flutter"),
    (r"\bdart\b", "Dart"),
    (r"\bsqlite\b", "SQLite"),
    (r"\bmongo(db)?\b", "MongoDB"),
    (r"\bmysql\b", "MySQL"),
    (r"\bhtml5?\b", "HTML"),
    (r"\bcss3?\b", "CSS"),
    (r"\bsass\b", "Sass"),
    (r"\btailwind\b", "Tailwind CSS"),
    (r"\bapi( rest)?\b", "API REST"),
    (r"\bjson rpc\b", "JSON-RPC"),
    (r"\bgraphql\b", "GraphQL"),
    (r"\bgit\b", "Git"),
    (r"\bgithub actions\b", "GitHub Actions"),
    (r"\bci/cd\b", "CI/CD"),
    (r"\bdocker\b", "Docker"),
    (r"\bkubernetes\b", "Kubernetes"),
    (r"\bterraform\b", "Terraform"),
    (r"\bansible\b", "Ansible"),
    (r"\baws\b", "AWS"),
    (r"\bazure\b", "Azure"),
    (r"\bgcp\b|google cloud", "Google Cloud"),
    (r"\bproxmox\b", "Proxmox"),
    (r"\blinux\b", "Linux"),
    (r"\bnginx\b|caddy", "Reverse proxy (Nginx/Caddy)"),
    (r"\bstripe\b", "Stripe"),
    (r"\bpaypal\b", "PayPal"),
    (r"\bodoo\b", "Odoo"),
    (r"\bexcel\b", "Excel"),
    (r"\bgoogle sheets\b", "Google Sheets"),
    (r"\bfigma\b", "Figma"),
    (r"\bphotoshop\b", "Photoshop"),
    (r"\bseo\b", "SEO"),
    (r"\badwords\b|google ads", "Google Ads"),
    (r"\bgoogle analytics\b", "Google Analytics"),
    (r"\bmarketing\b", "Marketing"),
    (r"\bredaction\b|copywriting", "Rédaction / copywriting"),
    (r"\bcommunica[nt]{2}", "Communication"),
    (r"\banglais\b", "Anglais"),
    (r"\bfrançais\b|french", "Français"),
    (r"\bgestion de projet\b|project management", "Gestion de projet"),
    (r"\bagile\b|scrum", "Agile / Scrum"),
    (r"\bkanban\b", "Kanban"),
    (r"\btest(s)?\b|qa\b", "Tests / QA"),
    (r"\bmachine learning\b", "Machine learning"),
    (r"\bdeep learning\b", "Deep learning"),
    (r"\bllm\b|large language model", "LLM (grands modèles de langage)"),
    (r"\bagent(s)? ia\b|agents ia|ai agents", "Agents IA"),
    (r"\bia\b|intelligence artificielle|artificial intelligence", "IA appliquée"),
    (r"\bnlp\b", "NLP"),
    (r"\bchatbot", "Chatbot"),
    (r"\bdata\b|analyse de données|data analysis", "Data / Analyse"),
    (r"\bpower bi\b", "Power BI"),
    (r"\btableau\b", "Tableau"),
    (r"\bspring boot\b", "Spring Boot"),
    (r"\bjava\b", "Java"),
    (r"\bc#\b|\.net", "C# / .NET"),
    (r"\bsalesforce\b", "Salesforce"),
    (r"\bsap\b", "SAP"),
    (r"\bhubspot\b", "HubSpot"),
    (r"\bcrm\b", "CRM"),
    (r"\berp\b", "ERP"),
    (r"\bwin dev\b|windev", "WinDev / WLangage"),
    (r"\bwordpress\b", "WordPress"),
    (r"\bshopify\b", "Shopify"),
    (r"\bseo\b", "SEO"),
]

# Les quêtes de base : le socle de carrière, indépendant de l'offre.
QUETES_BASE = [
    ("Pitch de 30 secondes",
     "Rédige et répète ton pitch personnel. Pourquoi toi ? En 30 secondes chrono.",
     "carriere", 10),
    ("Audit LinkedIn",
     "Ouvre ton profil LinkedIn. Trois choses à améliorer : photo, bannière, résumé.",
     "carriere", 10),
    ("Mise à jour du CV",
     "Ajoute ta dernière réalisation au CV. Une ligne de plus, une compétence de plus.",
     "carriere", 10),
    ("Histoire de projet",
     "Prépare l'histoire d'un projet compliqué que tu as mené. Situation, action, résultat chiffré.",
     "carriere", 15),
    ("Veille sur l'entreprise",
     "Note ce que cherche l'entreprise, son produit, ses concurrents. Trois points à citer en entretien.",
     "carriere", 10),
]


class QueteDomaine(models.Model):
    _name = "quete.domaine"
    _description = "Domaine de la roue de vie"
    _order = "sequence, id"

    name = fields.Char("Domaine", required=True)
    emoji = fields.Char("Emoji", default="🎯")
    sequence = fields.Integer(default=10)
    nb_quetes = fields.Integer("Quêtes en cours", compute="_compter")
    nb_faites = fields.Integer("Quêtes faites", compute="_compter")

    @api.depends("quete_ids.etat")
    def _compter(self):
        for d in self:
            d.nb_quetes = len(d.quete_ids.filtered(lambda q: q.etat != "faite"))
            d.nb_faites = len(d.quete_ids.filtered(lambda q: q.etat == "faite"))

    quete_ids = fields.One2many("quete.fiche", "domaine_id", "Quêtes")


class QueteGuilde(models.Model):
    _name = "quete.guilde"
    _description = "Guilde : un groupe de membres rassemblés par un objectif"
    _order = "sequence, id"

    name = fields.Char("Nom de la guilde", required=True)
    embleme = fields.Char("Emblème", default="⚔️")
    objectif = fields.Text("L'objectif")
    sequence = fields.Integer(default=10)
    membre_ids = fields.Many2many(
        "equipe.membre", string="Membres",
        help="Les membres de l'équipage qui travaillent à cet objectif.")
    active = fields.Boolean("Active", default=True)
    quete_ids = fields.One2many("quete.fiche", "guilde_id", "Quêtes")
    nb_quetes = fields.Integer("Quêtes", compute="_compter")
    nb_faites = fields.Integer("Faites", compute="_compter")

    @api.depends("quete_ids.etat")
    def _compter(self):
        for g in self:
            g.nb_quetes = len(g.quete_ids)
            g.nb_faites = len(g.quete_ids.filtered(lambda q: q.etat == "faite"))


class QueteOffre(models.Model):
    _name = "quete.offre"
    _description = "Offre d'emploi transformée en quêtes"
    _order = "create_date desc, id desc"

    name = fields.Char("Le poste", required=True)
    entreprise = fields.Char("L'entreprise")
    texte = fields.Text("L'offre, collée telle quelle", required=True)
    etat = fields.Selection(
        [("nouvelle", "Nouvelle"),
         ("generee", "Quêtes générées")],
        "État", default="nouvelle")
    skills = fields.Text("Compétences détectées", readonly=True)
    nb_skills = fields.Integer("Skills couvertes", compute="_compter")
    couverture = fields.Char("Couverture", compute="_compter")
    quete_ids = fields.One2many("quete.fiche", "offre_id", "Quêtes générées")
    nb_quetes = fields.Integer("Quêtes", compute="_compter")
    nb_faites = fields.Integer("Faites", compute="_compter")

    @api.depends("skills", "quete_ids.etat")
    def _compter(self):
        for o in self:
            liste = [s.strip() for s in (o.skills or "").split("|") if s.strip()]
            o.nb_skills = len(liste)
            o.nb_quetes = len(o.quete_ids)
            o.nb_faites = len(o.quete_ids.filtered(lambda q: q.etat == "faite"))
            o.couverture = "%d/%d skills couvertes" % (o.nb_skills, o.nb_skills)

    # ------------------------------------------------------------------
    @api.model
    def _extraire_skills(self, texte):
        """Retourne la liste ORDONNÉE des skills trouvées (sans doublon)."""
        texte = texte or ""
        texte = " " + texte.lower() + " "
        trouvees = []
        vues = set()
        for motif, nom in SKILL_LEXIQUE:
            if re.search(motif, texte):
                if nom not in vues:
                    vues.add(nom)
                    trouvees.append(nom)
        return trouvees

    def action_generer_quetes(self):
        """Génère les quêtes : une par skill détectée + le socle de carrière."""
        self.ensure_one()
        if not (self.texte or "").strip():
            raise ValueError(_("Colle d'abord le texte de l'offre."))
        if self.etat == "generee":
            # Régénérer : on repart de zéro, sans empiler les doublons.
            self.quete_ids.unlink()
        skills = self._extraire_skills(self.texte)
        self.write({"skills": "|".join(skills), "etat": "generee"})

        Domaine = self.env["quete.domaine"].sudo()
        carriere = Domaine.search([("name", "=", "Carrière")], limit=1)
        formation = Domaine.search([("name", "=", "Formation")], limit=1)

        Quete = self.env["quete.fiche"].sudo()
        quetes = []
        for titre, desc, nom_domaine, xp in QUETES_BASE:
            domaine = carriere if nom_domaine == "carriere" else formation
            quetes.append((0, 0, {
                "name": titre, "description": desc, "xp": xp,
                "domaine_id": domaine.id, "offre_id": self.id,
                "source": "base",
            }))
        for skill in skills:
            quetes.append((0, 0, {
                "name": "Maîtrise — %s" % skill,
                "description": ("Approfondis « %s » jusqu'à pouvoir le défendre "
                                "en entretien : une ressource, une prise en "
                                "main, un exemple concret, une question "
                                "d'auto-contrôle." % skill),
                "xp": 15, "domaine_id": (formation or carriere).id,
                "offre_id": self.id, "source": "offre", "skill": skill,
            }))
        self.write({"quete_ids": quetes})
        return True

    def action_regenerer(self):
        self.ensure_one()
        return self.action_generer_quetes()


class QueteFiche(models.Model):
    _name = "quete.fiche"
    _description = "Une quête"
    _inherit = ["mail.thread"]
    _order = "etat, create_date desc, id desc"

    name = fields.Char("La quête", required=True)
    description = fields.Text("Description")
    xp = fields.Integer("XP", default=10)
    etat = fields.Selection(
        [("a_faire", "À faire"),
         ("en_cours", "En cours"),
         ("faite", "Faite")],
        "État", default="a_faire")
    domaine_id = fields.Many2one("quete.domaine", "Domaine",
                                 ondelete="set null", index=True)
    guilde_id = fields.Many2one("quete.guilde", "Guilde",
                                ondelete="set null", index=True)
    offre_id = fields.Many2one("quete.offre", "Offre d'origine",
                               ondelete="cascade", index=True)
    source = fields.Selection(
        [("base", "Socle de carrière"), ("offre", "Issue d'une offre")],
        "Source", default="base")
    skill = fields.Char("Compétence couverte",
                        help="La skill de l'offre que cette quête travaille.")
    date_faite = fields.Datetime("Terminée le", readonly=True)

    def action_terminer(self):
        """Termine la quête. L'XP n'est PAS posée ici : le compteur
        « quêtes de carrière » la mesure (search_count des quêtes faites) et
        la relève consigne le gain dans equipe.exploit. Un point sans registre
        n'existe pas."""
        for q in self:
            q.write({"etat": "faite", "date_faite": fields.Datetime.now()})
            q.message_post(body=_("Quête terminée : %s (+%s XP).", q.name, q.xp))
        return True

    def action_relancer(self):
        for q in self:
            q.write({"etat": "a_faire", "date_faite": False})
        return True

    def action_en_cours(self):
        for q in self:
            q.write({"etat": "en_cours"})
        return True
