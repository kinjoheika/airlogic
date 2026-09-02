# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartnerDispatchExt(models.Model):
    _inherit = 'res.partner'

    airlogic_dispatch_zone_id = fields.Many2one(
        'airlogic.dispatch.zone', string='Service Zone',
        help='Which dispatch zone this client is in -- the proximity signal '
             'Rules 3 (nearest available crew) and 4 (zone sweep) use, since '
             'there is no real geolocation data.')
    airlogic_preferred_hours = fields.Char(
        string='Preferred Service Hours',
        help='Free text, e.g. "9am-11am, avoid 12-1pm lunch rush" -- read by '
             "Rule 5 (client time-window) as a note on the suggestion, not "
             'parsed into an exact time automatically.')
