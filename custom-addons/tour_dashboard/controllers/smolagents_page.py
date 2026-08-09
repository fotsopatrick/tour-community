# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Le panneau smolagents et la file (07/08, Patrick).

Patrick : « tu peux me faire une webapp et pas un artefact Claude ? tu mets le
lien dans mes actions sur la prod, dans accueil ».

Ce que cette page montre :

- les CHIFFRES VIVANTS, relus dans la base a chaque ouverture : l'etat de la
  file des messages, les missions qui bloquent l'atelier, les versions des
  modules, les decisions qui attendent. Ces chiffres bougent tout seuls.
- les MESURES DU 07/08 sur ce qu'il faut pour smolagents. Celles-la sont
  datees et affichees comme telles : un chiffre releve un jour et affiche
  comme s'il etait d'aujourd'hui, c'est un indicateur qui ment.

Meme verrou que le reste du cockpit : base.group_system.
"""
from urllib.parse import quote

from markupsafe import Markup

from odoo import http
from odoo.http import request

# Ce qui a ete MESURE le 07/08 en installant pour de vrai. Fige, et dit comme
# tel : ces valeurs ne se relisent pas toutes seules.
MESURES = [
    ("Un Python que smolagents accepte", "3.12.13",
     "installe par uv, a cote du 3.14", "ok"),
    ("Un gestionnaire d'environnements", "uv 0.12.2",
     "~/.local/bin/uv — sans sudo", "ok"),
    ("La bibliotheque", "smolagents 1.26.0",
     "/tmp/venv-smol — a deplacer, /tmp s'efface", "attente"),
    ("Le connecteur du modele", "smolagents[openai]",
     "DeepSeek parle le meme langage qu'OpenAI", "ok"),
    ("Une cle de modele", "presente",
     "dans le fichier de cles de l'atelier, droits 600", "ok"),
    ("De la place", "79 Mo",
     "l'image de l'atelier en prend 2 460", "ok"),
    ("Un endroit borne pour executer", "l_chloe",
     "1 utilisateur systeme sur 9", "attente"),
]

CONTROLES = [
    ("~/.local/bin/uv python list --only-installed",
     "Quelles versions de Python sont disponibles."),
    ("/tmp/venv-smol/bin/python -c 'import smolagents; print(smolagents.__version__)'",
     "smolagents s'importe ? Il doit repondre 1.26.0."),
    ("bash /tmp/essai-deepseek.sh | tail -4",
     "L'agent parle-t-il au moteur ? Il doit finir par REPONSE: 141."),
    ("cd ~/tour && python3 deploy/mcp-tour.py <<< '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}'",
     "opencode est branche ? On doit voir prendre_travail et rendre_compte."),
]

PANNES = [
    ("ModuleNotFoundError: openai", "Le connecteur manque",
     "uv pip install --python /tmp/venv-smol/bin/python 'smolagents[openai]'"),
    ("ensurepip is not available", "Le Python systeme refuse les venv (PEP 668)",
     "Passer par uv venv, jamais par python3 -m venv"),
    ("L'agent ne repond plus", "Cle absente ou reseau coupe",
     "Verifier que le fichier de cles de l'atelier est present et non vide"),
    ("Un message reste « pris »", "L'agent est mort en route",
     "Rien a faire : il repart seul en 15 min, puis devient une Decision"),
    ("Un agent ne recoit plus rien", "C'etait le bug des 4 lignes",
     "Corrige le 07/08. Regarder les missions en etat envoyee ci-dessus"),
]

GABARIT = u"""
<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Panneau — smolagents et la file</title>
<style>
:root{--ground:#f2f4f6;--surface:#fff;--surface2:#fafbfc;--line:#dde2e8;
--line2:#c3ccd6;--ink:#161a20;--ink2:#3d4854;--muted:#6b7684;--accent:#0f6f7a;
--accent-soft:#e2f1f2;--vert:#15803d;--vert-soft:#e3f4e9;--ambre:#9a6206;
--ambre-soft:#fbf0d9;--rouge:#b3261e;--rouge-soft:#fbe6e4;
--mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--ground:#0e1216;--surface:#161b21;--surface2:#1b2128;--line:#29323b;
--line2:#3b4650;--ink:#e7ecf1;--ink2:#b9c4cf;--muted:#8c98a5;--accent:#4fb3c0;
--accent-soft:#10333a;--vert:#5cc27f;--vert-soft:#12301f;--ambre:#d7a13e;
--ambre-soft:#322611;--rouge:#e8776d;--rouge-soft:#351a18}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.page{max-width:1080px;margin:0 auto;padding:30px 20px 70px}
header{border-bottom:2px solid var(--line2);padding-bottom:18px;margin-bottom:26px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;
text-transform:uppercase;color:var(--accent);margin:0 0 8px}
h1{margin:0 0 6px;font-size:clamp(24px,4vw,34px);line-height:1.14;
letter-spacing:-.02em;font-weight:640;text-wrap:balance}
.sous{margin:0;color:var(--muted);max-width:64ch}
.horodate{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:10px}
.bandeau{display:grid;gap:10px;margin:0 0 32px;
grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.jauge{background:var(--surface);border:1px solid var(--line);border-radius:3px;
padding:13px 14px;border-left:3px solid var(--line2)}
.jauge.ok{border-left-color:var(--vert)}
.jauge.attente{border-left-color:var(--ambre)}
.jauge.alerte{border-left-color:var(--rouge)}
.jauge .n{font-family:var(--mono);font-size:11px;color:var(--muted);
letter-spacing:.1em;text-transform:uppercase}
.jauge .v{font-family:var(--mono);font-size:26px;font-weight:600;
font-variant-numeric:tabular-nums;line-height:1.2;margin:4px 0 2px}
.jauge .t{font-size:13px;color:var(--ink2)}
.lampe{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);
font-size:11px;letter-spacing:.06em;text-transform:uppercase;
padding:2px 8px 2px 6px;border-radius:2px;white-space:nowrap}
.lampe::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.lampe.ok{color:var(--vert);background:var(--vert-soft)}
.lampe.attente{color:var(--ambre);background:var(--ambre-soft)}
.lampe.alerte{color:var(--rouge);background:var(--rouge-soft)}
section{margin:0 0 34px}
h2{font-size:13px;font-family:var(--mono);letter-spacing:.12em;
text-transform:uppercase;color:var(--ink2);margin:0 0 14px;padding-bottom:8px;
border-bottom:1px solid var(--line)}
p{margin:0 0 12px;max-width:68ch}
.muted{color:var(--muted)}
.cadre{overflow-x:auto;border:1px solid var(--line);border-radius:3px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:9px 13px;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-family:var(--mono);font-size:11px;letter-spacing:.09em;
text-transform:uppercase;color:var(--muted);background:var(--surface2);
font-weight:500;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
td.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.cmd{font-family:var(--mono);font-size:12.5px;line-height:1.6;
background:var(--surface2);border:1px solid var(--line);
border-left:3px solid var(--accent);border-radius:3px;padding:10px 13px;
overflow-x:auto;white-space:pre;margin:0 0 5px;color:var(--ink)}
.quoi{font-size:13px;color:var(--muted);margin:0 0 15px}
.preuve{background:var(--accent-soft);border:1px solid var(--line);
border-radius:3px;padding:14px 16px;margin:0 0 14px}
.preuve .titre{font-family:var(--mono);font-size:11px;letter-spacing:.1em;
text-transform:uppercase;color:var(--accent);margin-bottom:8px}
.preuve pre{margin:0;font-family:var(--mono);font-size:12.5px;line-height:1.55;
white-space:pre-wrap;color:var(--ink)}
.avert{border:1px solid var(--line);border-left:3px solid var(--ambre);
background:var(--ambre-soft);border-radius:3px;padding:12px 15px;margin:0 0 15px;max-width:74ch}
.retour{display:inline-block;font-family:var(--mono);font-size:12px;
color:var(--accent);text-decoration:none;border:1px solid var(--line);
padding:6px 12px;border-radius:3px;margin-bottom:20px}
.retour:hover,.retour:focus{background:var(--accent-soft);outline:2px solid var(--accent);outline-offset:1px}
.pilote{background:var(--surface);border:1px solid var(--line);border-radius:3px;
padding:16px 18px;margin:0 0 14px}
.pilote .rangee{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin-bottom:14px}
.champ{display:flex;flex-direction:column;gap:5px}
.champ label{font-family:var(--mono);font-size:11px;letter-spacing:.08em;
text-transform:uppercase;color:var(--muted)}
.champ input{font-family:var(--mono);font-size:15px;width:90px;padding:7px 9px;
border:1px solid var(--line2);border-radius:3px;background:var(--surface2);color:var(--ink)}
.champ .aide{font-size:12px;color:var(--muted);max-width:34ch}
button{font-family:var(--sans);font-size:14px;font-weight:560;padding:8px 15px;
border-radius:3px;border:1px solid var(--accent);background:var(--accent);
color:#fff;cursor:pointer}
button.second{background:var(--surface2);color:var(--accent)}
button:hover{filter:brightness(1.08)}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.actions{display:flex;flex-wrap:wrap;gap:10px;padding-top:14px;border-top:1px solid var(--line)}
.dit{border:1px solid var(--line);border-left:3px solid var(--vert);
background:var(--vert-soft);border-radius:3px;padding:11px 14px;margin:0 0 14px;
font-family:var(--mono);font-size:13px}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);
font-size:13px;color:var(--muted)}
</style></head><body><div class="page">
<a class="retour" href="/tour/dashboard">&larr; retour a l'accueil</a>
<header>
<p class="eyebrow">Tour de controle &middot; panneau d'etat</p>
<h1>smolagents et la file</h1>
<p class="sous">Ce qu'il faut pour faire tourner un agent, ce qui est deja pose, et les commandes pour le verifier toi-meme.</p>
<p class="horodate">Les chiffres du haut sont relus dans la base a chaque ouverture &middot; page ouverte le %(maintenant)s</p>
</header>
<div class="bandeau">%(jauges)s</div>
<section><h2>Ce qu'il fallait, et ce qu'on a &mdash; mesure le 07/08</h2>
<div class="cadre"><table><thead><tr><th>Il faut</th><th>On a</th><th>Ou</th><th>Etat</th></tr></thead>
<tbody>%(mesures)s</tbody></table></div>
<p class="muted">Ces valeurs ont ete relevees en installant pour de vrai, le 07/08. Elles ne se relisent pas toutes seules : pour les verifier aujourd'hui, prends les commandes plus bas.</p>
</section>
<section><h2>La preuve &mdash; un agent qui appelle un outil</h2>
<div class="preuve"><div class="titre">smolagents + DeepSeek + un outil &middot; 07/08</div>
<pre>Combien font 137 plus 4 ? Utilise l'outil additionner.

  Executing parsed code:
    result = additionner(a=137, b=4)
    final_answer(result)

  Final answer: 141
  [Step 1: Duration 2.26 s | Input tokens: 2 057 | Output tokens: 41]</pre></div>
<p class="muted">Ce qui compte n'est pas le calcul. Le modele a <em>ecrit du code Python</em>, la machine l'a execute, l'outil a repondu. En un pas, en deux secondes.</p>
</section>
<section><h2>Pilotage &mdash; les deux boutons qui changent quelque chose</h2>
%(pilotage)s
</section>
<section><h2>Les commandes pour verifier toi-meme</h2>%(controles)s</section>
<section><h2>Ce qui reste avant de dire que ca tourne</h2>
<div class="cadre"><table><tbody>
<tr><td>Sortir l'essai de <span class="mono">/tmp</span> &mdash; ce dossier est efface au redemarrage.</td></tr>
<tr><td>Brancher l'agent sur la file : prendre le travail, rendre le compte &mdash; comme opencode depuis le 07/08.</td></tr>
<tr><td>L'executer sous <span class="mono">l_&lt;agent&gt;</span>, jamais sous <span class="mono">ubuntu</span> : smolagents ecrit du Python et l'execute.</td></tr>
<tr><td>Comparer avant de remplacer : meme consigne sur l'ancienne boucle et sur lui. S'il ne fait pas mieux, on garde les 593 lignes.</td></tr>
</tbody></table></div>
<div class="avert">Le critere est ecrit <strong>avant</strong> l'essai, expres. Ce n'est pas un test pour valider une envie : c'est la regle du retest appliquee a un choix d'outil.</div>
</section>
<section><h2>Si ca casse</h2>
<div class="cadre"><table><thead><tr><th>Symptome</th><th>Cause probable</th><th>Le geste</th></tr></thead>
<tbody>%(pannes)s</tbody></table></div></section>
<section><h2>Les decisions qui attendent</h2>
<div class="cadre"><table><thead><tr><th>Fiche</th><th>Ce qu'elle propose</th></tr></thead>
<tbody>%(decisions)s</tbody></table></div></section>
<footer>Les chiffres du bandeau viennent de la base, maintenant. Le reste a ete mesure sur la machine le 07/08/2026, pas deduit.</footer>
</div></body></html>
"""


class TourSmolagents(http.Controller):

    # ------------------------------------------------------------------
    # LE PILOTAGE. Deux reglages et deux gestes, pas plus.
    # ------------------------------------------------------------------
    # Pourquoi si peu : une page qui offre vingt boutons n'est pas pilotable,
    # elle est intimidante. Ces quatre-la sont ceux qui changent vraiment
    # quelque chose, et chacun est reversible.
    @http.route("/tour/cockpit/smolagents/piloter", type="http", auth="user",
                methods=["POST"], website=False, csrf=False)
    def piloter(self, **kw):
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")

        geste = (kw.get("geste") or "").strip()
        dit = ""
        Param = env["ir.config_parameter"].sudo()

        if geste == "reglages":
            for cle, champ, mini, maxi in (
                ("tour_dashboard.minutes_anti_repetition", "silence", 0, 10080),
                ("tour_bus.minutes_atelier_occupe", "occupe", 1, 10080),
            ):
                brut = (kw.get(champ) or "").strip()
                if not brut:
                    continue
                try:
                    valeur = int(brut)
                except (TypeError, ValueError):
                    continue
                valeur = max(mini, min(maxi, valeur))
                Param.set_param(cle, str(valeur))
            dit = u"Reglages enregistres. Ils s'appliquent tout de suite, sans redemarrage."

        elif geste == "reprise":
            try:
                repris, bloques = env["tour.bus.message"].sudo()._cron_reprise()
                dit = (u"Reprise jouee : %s message(s) remis dans la file, "
                       u"%s bloque(s)." % (repris, bloques))
            except Exception as e:  # noqa: BLE001
                dit = u"La reprise n'a pas pu tourner : %s" % e

        elif geste == "depiler":
            try:
                n = env["tour.bus.message"].sudo()._cron_depiler_atelier()
                dit = u"%s mission(s) en attente partie(s) a l'atelier." % n
            except Exception as e:  # noqa: BLE001
                dit = u"Le depilage n'a pas pu tourner : %s" % e

        else:
            dit = u"Geste inconnu : rien n'a ete fait."

        return request.redirect(
            "/tour/cockpit/smolagents?dit=" + quote(dit))

    @http.route("/tour/cockpit/smolagents", type="http", auth="user",
                website=False, csrf=False)
    def panneau(self, **kw):
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")

        cr = env.cr

        def un(sql, defaut=0):
            """Un seul chiffre. Si la table n'existe pas, on rend le defaut
            plutot que de casser la page : une page blanche ne dit rien."""
            try:
                cr.execute(sql)
                ligne = cr.fetchone()
                return ligne[0] if ligne and ligne[0] is not None else defaut
            except Exception:  # noqa: BLE001
                cr.rollback()
                return defaut

        a_prendre = un("select count(*) from tour_bus_message where etat='nouveau'")
        pris = un("select count(*) from tour_bus_message where etat='pris'")
        bloques = un("select count(*) from tour_bus_message where etat='bloque'")
        occupe = un("select count(*) from atelier_mission where etat='envoyee'")
        attente = un("select count(*) from atelier_mission where etat='brouillon'")
        decisions = un("select count(*) from decision_fiche where etat='attente'")

        def jauge(n, valeur, texte, ton):
            return (u'<div class="jauge %s"><div class="n">%s</div>'
                    u'<div class="v">%s</div><div class="t">%s</div></div>'
                    % (ton, n, valeur, texte))

        jauges = u"".join([
            jauge(u"File &middot; a prendre", a_prendre,
                  u"messages que personne n'a pris",
                  "attente" if a_prendre else "ok"),
            jauge(u"File &middot; en cours", pris,
                  u"un agent travaille dessus", "ok"),
            jauge(u"File &middot; bloques", bloques,
                  u"trois echecs : une Decision t'attend",
                  "alerte" if bloques else "ok"),
            jauge(u"Atelier &middot; en cours", occupe,
                  u"au-dela d'une heure, ne bloque plus rien", "ok"),
            jauge(u"Missions en attente", attente,
                  u"elles partent des que l'atelier se libere",
                  "attente" if attente else "ok"),
            jauge(u"Decisions", decisions,
                  u"elles attendent ton approbation",
                  "attente" if decisions else "ok"),
        ])

        mesures = u"".join([
            u'<tr><td>%s</td><td class="mono">%s</td><td>%s</td>'
            u'<td><span class="lampe %s">%s</span></td></tr>'
            % (il_faut, on_a, ou, ton, u"pose" if ton == "ok" else u"a finir")
            for il_faut, on_a, ou, ton in MESURES
        ])

        controles = u"".join([
            u'<div class="cmd">%s</div><p class="quoi">%s</p>'
            % (c.replace("<", "&lt;").replace(">", "&gt;"), quoi)
            for c, quoi in CONTROLES
        ])

        pannes = u"".join([
            u'<tr><td>%s</td><td>%s</td><td class="mono">%s</td></tr>'
            % (s, c, g.replace("<", "&lt;").replace(">", "&gt;"))
            for s, c, g in PANNES
        ])

        lignes_dec = []
        try:
            cr.execute("select id, left(name,110) from decision_fiche "
                       "where etat='attente' order by id desc limit 8")
            for ident, nom in cr.fetchall():
                lignes_dec.append(u'<tr><td class="mono">#%s</td><td>%s</td></tr>'
                                  % (ident, (nom or u"").replace("<", "&lt;")))
        except Exception:  # noqa: BLE001
            cr.rollback()
        if not lignes_dec:
            lignes_dec.append(u'<tr><td colspan="2">Aucune decision en attente.</td></tr>')

        # ---- le pilotage : les valeurs actuelles, puis la commande ----
        Param = env["ir.config_parameter"].sudo()
        silence = Param.get_param("tour_dashboard.minutes_anti_repetition") or "120"
        occupe_min = Param.get_param("tour_bus.minutes_atelier_occupe") or "60"
        dit = (kw.get("dit") or "").strip()[:300]

        pilotage = u""
        if dit:
            pilotage += u'<div class="dit">%s</div>' % dit.replace("<", "&lt;")
        pilotage += (
            u'<form class="pilote" method="post" action="/tour/cockpit/smolagents/piloter">'
            u'<input type="hidden" name="geste" value="reglages"/>'
            u'<div class="rangee">'
            u'<div class="champ"><label for="silence">Silence des alertes</label>'
            u'<input id="silence" name="silence" type="number" min="0" max="10080" value="%s"/>'
            u'<span class="aide">minutes pendant lesquelles la meme alerte ne '
            u'repart pas par courriel. 0 = tout repart, comme avant. '
            u'C\'est ce reglage qui a arrete les 867 courriels.</span></div>'
            u'<div class="champ"><label for="occupe">Atelier occupe</label>'
            u'<input id="occupe" name="occupe" type="number" min="1" max="10080" value="%s"/>'
            u'<span class="aide">minutes au-dela desquelles une mission en cours '
            u'cesse de bloquer les autres. Trop court : on double le travail. '
            u'Trop long : un agent mort bloque les vivants.</span></div>'
            u'<button type="submit">Enregistrer</button>'
            u'</div></form>'
            u'<div class="actions">'
            u'<form method="post" action="/tour/cockpit/smolagents/piloter">'
            u'<input type="hidden" name="geste" value="reprise"/>'
            u'<button class="second" type="submit">Remettre en file ce qui traine</button>'
            u'</form>'
            u'<form method="post" action="/tour/cockpit/smolagents/piloter">'
            u'<input type="hidden" name="geste" value="depiler"/>'
            u'<button class="second" type="submit">Envoyer les missions en attente</button>'
            u'</form>'
            u'</div>'
        ) % (silence, occupe_min)
        pilotage += (
            u'<p class="muted">Les deux boutons ne font rien de neuf : ils jouent '
            u'tout de suite ce que les crons font deja toutes les cinq minutes. '
            u'Les relancer a la main ne casse rien &mdash; c\'est fait pour.</p>')

        # PIEGE (07/08, trouve en prod : erreur 500). On NE FAIT PAS
        # « GABARIT % {...} » : la feuille de style contient des pourcentages
        # (border-radius:50%, width:100%) et le formatage de Python essaie de
        # les lire comme des codes. On substitue les jetons a la main : aucun
        # caractere n'est interprete.
        from odoo import fields as of
        html = GABARIT
        for cle, valeur in (
            ("maintenant", of.Datetime.now().strftime("%d/%m/%Y a %H:%M")),
            ("jauges", jauges),
            ("mesures", mesures),
            ("pilotage", pilotage),
            ("controles", controles),
            ("pannes", pannes),
            ("decisions", u"".join(lignes_dec)),
        ):
            html = html.replace(u"%(" + cle + u")s", valeur)
        return request.make_response(
            Markup(html), headers=[("Content-Type", "text/html; charset=utf-8")])
