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
    def action_verify_field_pin(self, *args, **kwargs):
        """Always checks the CALLING user's own PIN (self.env.user),
        regardless of which record self is bound to -- avoids the JS
        side needing to know its own uid via a service/global that's
        proven unreliable on this build.

        Takes *args instead of a plain `pin` positional param: this
        build's call_kw dispatch has been inconsistent about whether it
        strips a leading ids placeholder from the JS orm.call args list
        before invoking @api.model methods (confirmed inconsistent by
        action_am_i_field_manager below, which received one more
        positional argument than its own zero-param signature allows).
        Taking the LAST positional arg is convention-agnostic: the pin
        value is always the last thing sent from the JS side, whether or
        not an ids placeholder precedes it.
        """
        pin = args[-1] if args else kwargs.get('pin')
        user = self.env.user
        if not user.airlogic_field_pin:
            return True
        return pin == user.airlogic_field_pin

    @api.model
    def action_am_i_field_manager(self, *args, **kwargs):
        """core has_group() calls self.ensure_one() on this build, so it
        can't be called on an empty/unbound recordset from the JS side
        (self.env['res.users'].has_group(...) errors: Expected singleton).
        self.env.user is always a real singleton, so wrap it here instead.

        Takes *args, **kwargs (all ignored) purely defensively: this
        method has no real parameters, but call_kw on this build has
        been observed passing an extra positional argument even when the
        JS side sends an empty ids placeholder ([[]]) -- see the note on
        action_verify_field_pin above.
        """
        return self.env.user.has_group('airlogic_core.group_airlogic_manager')
