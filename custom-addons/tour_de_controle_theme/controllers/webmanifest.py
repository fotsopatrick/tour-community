from odoo.addons.web.controllers.webmanifest import WebManifest


class TdcWebManifest(WebManifest):
    """PWA manifest aux couleurs de la tour de contrôle (le nom vient du
    paramètre système ``web.web_app_name``, posé par data/debrand_parameters)."""

    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        manifest.update(
            {
                "background_color": "#020817",
                "theme_color": "#020817",
                "icons": [
                    {
                        "src": "/tour_de_controle_theme/static/src/img/app-icon-%s.png" % size,
                        "sizes": "%sx%s" % (size, size),
                        "type": "image/png",
                    }
                    for size in (192, 512)
                ],
            }
        )
        return manifest
