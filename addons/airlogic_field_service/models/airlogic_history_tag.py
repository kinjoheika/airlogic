# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicHistoryTag(models.Model):
    """Configurable keyword filter driving the mobile app's History tab.
    A job only shows up in Unit History if its notes or a flagged/alert
    checklist item's note match one of these tags' keywords -- keeps the
    feed to a handful of major events per year instead of every visit,
    entirely controlled by how broad/narrow the keyword lists are.
    """
    _name = 'airlogic.history.tag'
    _description = 'Airlogic Unit History Tag'
    _order = 'sequence, name'

    name = fields.Char(required=True, help='e.g. "Replaced Part", "Cannot Power On"')
    keywords = fields.Char(
        required=True,
        help='Comma-separated keywords/phrases, matched case-insensitively '
             'against job notes and flagged/alert checklist item notes. '
             'e.g. "replace, replaced, swapped"')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
