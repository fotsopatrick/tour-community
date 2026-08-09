# -*- coding: utf-8 -*-
"""Force Secure sur le cookie de session.

Le build Odoo 18.0 pose le cookie session_id avec HttpOnly mais sans Secure,
meme derriere un proxy HTTPS. Le flag Secure empeche le cookie de partir sur
une connexion en clair si une route http existait un jour.

Patch au chargement du module : on ajoute secure=True sur le cookie
session_id, et seulement sur lui. Tous les autres cookies gardent le
comportement d'origine.
"""

import werkzeug.wrappers

_orig_set_cookie = werkzeug.wrappers.Response.set_cookie


def _set_cookie_secure(self, key, *args, **kwargs):
    if key == "session_id":
        kwargs["secure"] = True
    return _orig_set_cookie(self, key, *args, **kwargs)


werkzeug.wrappers.Response.set_cookie = _set_cookie_secure
