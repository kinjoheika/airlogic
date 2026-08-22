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
        help='PIN required in the mobile Field Service app: before the '
             'client list, before opening a device\'s entry screen, and '
             '(for Senior Technicians) before Add/Delete Equipment. '
             'Leave blank to skip the PIN gate for this user.')
    airlogic_is_senior_technician = fields.Boolean(
        string='Senior Technician (Field App)',
        help='Only Senior Technicians can add or delete equipment from the '
             'mobile Field Service app -- everyone else can view units and '
             'record readings, but the Add/Delete Equipment tab stays '
             'locked behind this role plus their Field App PIN. Equipment '
             'added this way still goes through the Manager\'s normal '
             'review in Inventory > Equipment.')

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
    def action_verify_senior_tech_pin(self, *args, **kwargs):
        """Gate for the mobile app's Add/Delete Equipment tab: passes only
        if the calling user is flagged Senior Technician AND their Field
        App PIN matches (reuses the same PIN field/UX as the other two
        gates, just with the extra role check). A non-senior user gets the
        same "incorrect PIN" outcome as a wrong PIN, rather than a separate
        "not allowed" message -- keeps the one PIN screen doing double
        duty without leaking which reason it failed for.

        Unlike action_verify_field_pin, a blank PIN does NOT pass through
        here: Add/Delete is the one gate that must not be skippable just
        because a Senior Technician forgot to set a PIN.
        """
        pin = args[-1] if args else kwargs.get('pin')
        user = self.env.user
        if not user.airlogic_is_senior_technician or not user.airlogic_field_pin:
            return False
        return pin == user.airlogic_field_pin
