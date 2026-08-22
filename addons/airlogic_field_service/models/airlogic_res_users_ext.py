# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsersFieldServiceExt(models.Model):
    """Lightweight PIN gate for the mobile Field Service app -- NOT the
    Odoo login password, and stored in plain text deliberately: this is a
    quick-relock friction gate against someone picking up an unlocked
    phone, not a cryptographic secret. If a technician has no PIN set,
    the gate passes through (no lockout for people who haven't opted in).
    """
    _inherit = 'res.users'

    airlogic_field_pin = fields.Char(
        string='Field App PIN',
        help='PIN required twice in the mobile Field Service app: before '
             'the client list, and before opening a device\'s entry '
             'screen. Leave blank to skip the PIN gate for this user.')

    def action_verify_field_pin(self, pin):
        self.ensure_one()
        if not self.airlogic_field_pin:
            return True
        return pin == self.airlogic_field_pin
