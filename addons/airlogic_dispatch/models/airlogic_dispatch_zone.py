# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicDispatchZone(models.Model):
    """A named sub-area of a city, tagged on a client (res.partner) and
    used as the dispatch engine's proximity signal: there is no real
    geolocation/routing data in this system, so "near" is approximated
    as "same zone", and a technician's presence in a zone on a given
    day is inferred from whichever visits are already scheduled there
    that day (see airlogic.dispatch.request._find_nearest_technician),
    not from a separately assigned home territory.
    """
    _name = 'airlogic.dispatch.zone'
    _description = 'Airlogic Dispatch Zone'
    _order = 'city, sequence, name'

    name = fields.Char(required=True)
    city = fields.Selection([
        ('makati', 'Makati City'),
        ('pasay', 'Pasay City'),
        ('ermita', 'Ermita, Manila'),
    ], required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
