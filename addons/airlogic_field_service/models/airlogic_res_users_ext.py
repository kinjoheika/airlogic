# -*- coding: utf-8 -*-
from odoo import api, fields, models


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

    @api.model
    def action_verify_field_pin(self, pin):
        """Always checks the CALLING user's own PIN (self.env.user),
        regardless of which record self is bound to -- avoids the JS
        side needing to know its own uid via a service/global that's
        proven unreliable on this build. Same calling pattern as the
        already-working has_group RPC: no ids in the JS call at all.
        """
        user = self.env.user
        if not user.airlogic_field_pin:
            return True
        return pin == user.airlogic_field_pin

    @api.model
    def action_am_i_field_manager(self):
        """core has_group() calls self.ensure_one() on this build, so it
        can't be called on an empty/unbound recordset from the JS side
        (self.env['res.users'].has_group(...) errors: Expected singleton).
        self.env.user is always a real singleton, so wrap it here instead.
        """
        return self.env.user.has_group('airlogic_core.group_airlogic_manager')
