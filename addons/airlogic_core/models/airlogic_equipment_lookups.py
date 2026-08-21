# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicSublocation(models.Model):
    """Configurable sublocation list (e.g. Rooftop Parking, 3rd Floor
    Server Room), picked on equipment instead of typed as free text.
    """
    _name = 'airlogic.sublocation'
    _description = 'Airlogic Sublocation'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class AirlogicEquipmentBrand(models.Model):
    _name = 'airlogic.equipment.brand'
    _description = 'Airlogic Equipment Brand'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class AirlogicEquipmentHp(models.Model):
    _name = 'airlogic.equipment.hp'
    _description = 'Airlogic Equipment HP'
    _order = 'sequence, id'

    name = fields.Char(string='HP', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
