from . import models
from . import controllers


def post_init_hook(env):
    """Branche la « détection de compétence » sur TOUS les agents actifs.

    Patrick (31/07) : « branche cette compétence à tous les agents, que
    toutes leurs prochaines actions apparaissent sous forme de circuit ».

    Chaque membre reçoit la compétence `detection_circuits` (compteur partagé
    : chaque gabarit proposé en brouillon est une capacité vue). On crée sous
    le contexte install_mode pour que le hook de détection ne fabrique pas un
    brouillon pour chacune de ces compétences de seed.
    """
    Membre = env["equipe.membre"].sudo()
    Comp = env["equipe.competence"].sudo().with_context(install_mode=True)
    for m in Membre.search([("active", "=", True)]):
        if Comp.search([("membre_id", "=", m.id),
                        ("code", "=", "detection_circuits")], limit=1):
            continue
        Comp.create({
            "membre_id": m.id,
            "name": "Circuits proposés (détection)",
            "code": "detection_circuits",
            "sequence": 20,
        })
