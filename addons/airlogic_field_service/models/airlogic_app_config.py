# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AirlogicAppConfig(models.Model):
    """Single-record app-wide settings for the mobile Field Service app.
    Currently just the background wallpaper (Configuration > App
    Wallpaper) -- kept as its own tiny model, same pattern as History
    Tags/Measurement Fields, rather than bolted onto res.company, so it
    stays scoped to this app and easy to find.
    """
    _name = 'airlogic.app.config'
    _description = 'Airlogic Mobile App Configuration'

    name = fields.Char(default='Mobile App Settings', required=True)
    wallpaper = fields.Image(string='Background Wallpaper', max_width=1600, max_height=1600)

    @api.model
    def get_wallpaper_url(self):
        """Called from the mobile app on load. Returns a cache-busted
        image URL, or False if no wallpaper has been set -- the app
        falls back to its plain white background either way.
        """
        config = self.search([], limit=1)
        if not config or not config.wallpaper:
            return False
        return '/web/image/airlogic.app.config/%d/wallpaper?unique=%s' % (
            config.id, config.write_date.timestamp())
