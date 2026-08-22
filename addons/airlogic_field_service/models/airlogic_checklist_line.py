# -*- coding: utf-8 -*-
from odoo import fields, models

# Mirrors the PHASES constant in static/src/field_entry/field_entry.js --
# keep both in sync by hand. Not exposed as Configuration data (unlike
# airlogic.measurement.field); the user didn't ask for these items to be
# admin-editable, so they stay a fixed list, same as the mockup's own
# hardcoded checklist.
#
# Ported from the mockup's actual mobile DSR flow (tab-mobile,
# #pp-dsr / dsp-ph1..4), which turned out to differ from the desktop
# Equipment Data table's checklist this was originally built against:
# electrical readings sit inside the same phase as their power-state
# visual checks, and there's a Megger insulation test (Ph2) that wasn't
# modeled before.
CHECKLIST_ITEMS = [
    # Phase 1 -- Outdoor, Power ON
    (1, 'amp_draw', 'Amp Draw', 'number', 'A'),
    (1, 'cfm_outdoor', 'Anemometer (Outdoor)', 'number', 'CFM'),
    # Phase 2 -- Outdoor, Power OFF (visual) + Megger insulation test
    (2, 'brk', 'Breaker Wires & Terminals', 'check', None),
    (2, 'comp', 'Compressor Body', 'check', None),
    (2, 'coils', 'Coils & Fins', 'check', None),
    (2, 'motor', 'Motor & Fan', 'check', None),
    (2, 'pcb', 'PCB', 'check', None),
    (2, 'ipm', 'IPM', 'check', None),
    (2, 'wires', 'Wires & Terminals', 'check', None),
    (2, 'cables', 'Cable Ties / Paste / Grommets', 'check', None),
    (2, 'meg_u', 'Megger U Phase', 'number', 'MΩ'),
    (2, 'meg_v', 'Megger V Phase', 'number', 'MΩ'),
    (2, 'meg_w', 'Megger W Phase', 'number', 'MΩ'),
    # Phase 3 -- Indoor Unit (combined ON/OFF)
    (3, 'cfm_indoor', 'Anemometer (Indoor)', 'number', 'CFM'),
    (3, 'coil', 'Coil & Fins', 'check', None),
    (3, 'drain', 'Drain Pan', 'check', None),
    (3, 'drainline', 'Drain Line', 'check', None),
    (3, 'blower', 'Blower Fan', 'check', None),
    (3, 'fanmotor', 'Fan Motor', 'check', None),
    (3, 'wires_in', 'Wires', 'check', None),
    # Phase 4 -- Line Set + Submit
    (4, 'ins', 'Insulation Tape', 'check', None),
    (4, 'wire_cond', 'Wire Condition', 'check', None),
    (4, 'cond', 'Condensation', 'check', None),
    (4, 'leak', 'Leak Check', 'leak', None),
    (4, 'notes', 'Technician Notes', 'text', None),
]

# 7 leak-detector check spots (Leak Check step, Ph4), split into the two
# zones shown in the mockup's leak map.
LEAK_SPOTS = [
    (0, 'Indoor Unit'), (1, 'Indoor Unit'), (2, 'Indoor Unit'),
    (3, 'Condenser'), (4, 'Condenser'), (5, 'Condenser'), (6, 'Condenser'),
]


class AirlogicChecklistLine(models.Model):
    """One value for one Ph1-4 checklist item on one job. Saved by the
    field-entry OWL apps via
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
    value = fields.Char(
        string='Value',
        help="'ok'/'alert'/'flagged' for check items, a number for number "
             "items, comma-separated spot indices (or 'pass') for the leak "
             "check, free text for the notes item.")
    note = fields.Char(string='Note', help='Optional note, mainly for alert/flagged check items.')
