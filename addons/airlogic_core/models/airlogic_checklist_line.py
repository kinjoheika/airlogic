# -*- coding: utf-8 -*-
from odoo import fields, models

# Mirrors the PHASES constant in
# static/src/field_entry/field_entry.js -- keep both in sync by hand.
# Not exposed as Configuration data (unlike airlogic.measurement.field);
# the user didn't ask for these 21 items to be admin-editable, so they
# stay a fixed list, same as the mockup's own hardcoded checklist.
CHECKLIST_ITEMS = [
    (1, 'brk', 'Breaker Wires & Terminals'),
    (1, 'comp', 'Compressor Body'),
    (1, 'coils', 'Coils & Fins'),
    (1, 'motor', 'Motor & Fan'),
    (1, 'pcb', 'PCB'),
    (1, 'ipm', 'IPM'),
    (1, 'wires', 'Wires & Terminals'),
    (1, 'cables', 'Cable Ties / Paste / Grommets'),
    (2, 'volt', 'Line Voltage'),
    (2, 'a1', 'Amp Draw L1'),
    (2, 'a2', 'Amp Draw L2'),
    (2, 'a3', 'Amp Draw L3'),
    (3, 'cfm', 'Anemometer'),
    (3, 'coil', 'Coil & Fins'),
    (3, 'drain', 'Drain Pan'),
    (3, 'wiresIn', 'Wires (tactile)'),
    (4, 'ins', 'Insulation Tape'),
    (4, 'wireCond', 'Wire Condition'),
    (4, 'cond', 'Condensation'),
    (4, 'leak', 'Leak Check'),
    (4, 'notes', 'Tech Notes'),
]


class AirlogicChecklistLine(models.Model):
    """One value for one Ph1-4 visual-checklist item on one job. Saved by
    the airlogic_visual_checklist OWL client action via
    airlogic.service.job.action_save_visual_checklist().
    """
    _name = 'airlogic.checklist.line'
    _description = 'Airlogic Visual Checklist Line'
    _order = 'phase, id'

    job_id = fields.Many2one(
        'airlogic.service.job', string='Job', required=True, ondelete='cascade')
    phase = fields.Integer(string='Phase')
    key = fields.Char(string='Key', required=True)
    label = fields.Char(string='Item')
    value = fields.Char(string='Value')
