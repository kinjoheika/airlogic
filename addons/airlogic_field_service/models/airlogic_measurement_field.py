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
    pdf_label = fields.Char(
        string='PDF Label',
        help='Exact label text as it appears in a Fieldpiece JobLink PDF '
             'report, only if it differs from Label above (e.g. Label '
             '"Delta T (T1-T2)" but the PDF prints "T1-T2"). Leave blank '
             'to match on Label.')
    standard = fields.Char(
        string='Mfr. Standard',
        help='Expected/manufacturer standard shown as a hint next to the '
             'entered value, e.g. "≥ 8 °C". Leave blank for N/A.')
    min_value = fields.Float(
        string='Min (Pass/Fail)',
        help='Auto-flags a reading below this number as out of range. '
             'Leave at 0 for no minimum -- 0 itself is treated as "not '
             'set" here, so this field is not suitable for a field whose '
             'real lower bound is exactly zero.')
    max_value = fields.Float(
        string='Max (Pass/Fail)',
        help='Auto-flags a reading above this number as out of range. '
             'Leave at 0 for no maximum. This is the structured pass/fail '
             'threshold used for auto-flagging -- Mfr. Standard above is '
             'just a descriptive hint text, not compared against.')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)

    # Odoo 19 dropped _sql_constraints (fatal "Failed to load registry" on
    # this instance's SH strict mode). Use models.Constraint instead.
    _code_unique = models.Constraint(
        'UNIQUE(code)',
        'Measurement field code must be unique.',
    )
