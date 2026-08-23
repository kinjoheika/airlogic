# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AirlogicReadingLine(models.Model):
    """One measured value for one job. Kept as Char rather than Float so a
    single column can hold numbers, blanks, and Fieldpiece's non-numeric
    'OL' (over-limit) reading without special-casing storage per field.
    """
    _name = 'airlogic.reading.line'
    _description = 'Airlogic Reading Line'
    _order = 'sequence, id'

    job_id = fields.Many2one(
        'airlogic.service.job', string='Job', required=True, ondelete='cascade')
    field_id = fields.Many2one(
        'airlogic.measurement.field', string='Measurement Field', required=True,
        ondelete='restrict')
    value = fields.Char(string='Value')
    section = fields.Char(related='field_id.section', string='Section', store=True, readonly=True)
    unit = fields.Char(related='field_id.unit', string='Unit', readonly=True)
    standard = fields.Char(related='field_id.standard', string='Mfr. Standard', readonly=True)
    sequence = fields.Integer(related='field_id.sequence', store=True, readonly=True)
    is_out_of_range = fields.Boolean(
        string='Out of Range', compute='_compute_is_out_of_range', store=True,
        help='True when the entered value parses as a number and falls '
             "outside the field's configured Min/Max (Configuration > "
             'Measurement Fields). Non-numeric values (blank, "OL", "-") '
             "and fields with no threshold set never flag -- there's "
             'nothing to compare.')

    @api.depends('value', 'field_id.min_value', 'field_id.max_value')
    def _compute_is_out_of_range(self):
        for line in self:
            line.is_out_of_range = False
            f = line.field_id
            if not line.value or (not f.min_value and not f.max_value):
                continue
            try:
                v = float(line.value)
            except ValueError:
                continue
            if f.min_value and v < f.min_value:
                line.is_out_of_range = True
            elif f.max_value and v > f.max_value:
                line.is_out_of_range = True

    def write(self, vals):
        """A Manager can edit measurements on an already-Submitted job
        (rule_reading_line_lock_submitted in airlogic_ir_rule.xml grants
        Manager an unconditional pass around the normal submission
        lock). There's no structured Revision record for this path the
        way there is for the technician-facing Request Correction flow,
        so log it to the job's own chatter instead, one line per changed
        value.
        """
        is_manager = self.env.user.has_group('airlogic_core.group_airlogic_manager')
        if is_manager and 'value' in vals:
            for line in self:
                if (line.job_id.state == 'submitted' and not line.job_id.revision_open
                        and vals['value'] != line.value):
                    line.job_id.message_post(body=_(
                        'Manager edit on submitted job: <b>%(field)s</b> changed from '
                        '"%(old)s" to "%(new)s".') % {
                        'field': line.field_id.display_name,
                        'old': line.value or '—', 'new': vals['value'] or '—'})
        return super().write(vals)
