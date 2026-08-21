# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicMeasurementField(models.Model):
    """Configurable definition of one row in the Fieldpiece JobLink
    measurement tool. Kept as data (not hardcoded model fields) so the
    30-field list can be reordered, relabeled, or extended from the
    Configuration menu without a code deploy.
    """
    _name = 'airlogic.measurement.field'
    _description = 'Airlogic Measurement Field'
    _order = 'sequence, id'

    name = fields.Char(string='Label', required=True)
    code = fields.Char(
        string='Code', required=True,
        help='Stable technical key, e.g. return_air_db. Used to match '
             'values when importing a Fieldpiece PDF report.')
    section = fields.Char(
        string='Section',
        help='Grouping header shown on the reading grid, '
             'e.g. Air Side, Refrigerant Side, Manometer Pressure.')
    unit = fields.Char(string='Unit', help="e.g. °C, psi, CFM. Leave blank for none.")
    standard = fields.Char(
        string='Mfr. Standard',
        help='Expected/manufacturer standard shown as a hint next to the '
             'entered value, e.g. "≥ 8 °C". Leave blank for N/A.')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Measurement field code must be unique.'),
    ]
