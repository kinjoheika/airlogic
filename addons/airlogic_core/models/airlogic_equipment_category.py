# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicEquipmentCategory(models.Model):
    """Aircon unit category (Split-Wall, Window, ...), carrying the flat
    per-unit service rate for that category. Replaces a hardcoded Selection
    so rates are editable data, not code -- same pattern as
    airlogic.measurement.field.
    """
    _name = 'airlogic.equipment.category'
    _description = 'Airlogic Equipment Category'
    _order = 'sequence, id'

    name = fields.Char(string='Category', required=True)
    rate = fields.Float(string='Rate per Unit', default=0.0)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
