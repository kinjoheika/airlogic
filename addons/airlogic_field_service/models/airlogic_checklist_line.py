# -*- coding: utf-8 -*-
from odoo import _, fields, models

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
    # Phase 1 -- Outdoor/Indoor ON: both anemometer readings taken here
    # (cfm_indoor moved from Phase 3, which is now OFF-only visual checks).
    (1, 'amp_draw', 'Amp Draw', 'number', 'A'),
    (1, 'cfm_outdoor', 'Anemometer (Outdoor)', 'number', 'CFM'),
    (1, 'cfm_indoor', 'Anemometer (Indoor)', 'number', 'CFM'),
    # Phase 2 -- Outdoor OFF: Megger insulation test first, then the
    # visual checks (reordered so the numbers get entered before the
    # power-off inspection, not buried after it).
    (2, 'meg_u', 'Megger U Phase', 'number', 'MΩ'),
    (2, 'meg_v', 'Megger V Phase', 'number', 'MΩ'),
    (2, 'meg_w', 'Megger W Phase', 'number', 'MΩ'),
    (2, 'brk', 'Breaker Wires & Terminals', 'check', None),
    (2, 'comp', 'Compressor Body', 'check', None),
    (2, 'coils', 'Coils & Fins', 'check', None),
    (2, 'motor', 'Motor & Fan', 'check', None),
    (2, 'pcb', 'PCB', 'check', None),
    (2, 'ipm', 'IPM', 'check', None),
    (2, 'wires', 'Wires & Terminals', 'check', None),
    (2, 'cables', 'Cable Ties / Paste / Grommets', 'check', None),
    # Phase 3 -- Indoor OFF
    (3, 'coil', 'Coil & Fins', 'check', None),
    (3, 'drain', 'Drain Pan', 'check', None),
    (3, 'drainline', 'Drain Line', 'check', None),
    (3, 'motor_fan', 'Motor & Fan', 'check', None),
    (3, 'wires_in', 'Wires & Sensors', 'check', None),
    # Phase 4 -- Lines
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

    def write(self, vals):
        """Same Manager-bypass logging as airlogic.reading.line.write() --
        see that method's docstring for why this logs to the job's
        chatter instead of a Revision record.
        """
        is_manager = self.env.user.has_group('airlogic_core.group_airlogic_manager')
        if is_manager and ('value' in vals or 'note' in vals):
            for line in self:
                if line.job_id.state != 'submitted' or line.job_id.revision_open:
                    continue
                changed = []
                if 'value' in vals and vals['value'] != line.value:
                    changed.append(_('value "%(old)s" to "%(new)s"') % {
                        'old': line.value or '—', 'new': vals['value'] or '—'})
                if 'note' in vals and vals['note'] != line.note:
                    changed.append(_('note "%(old)s" to "%(new)s"') % {
                        'old': line.note or '—', 'new': vals['note'] or '—'})
                if changed:
                    line.job_id.message_post(body=_(
                        'Manager edit on submitted job: <b>%(item)s</b> %(changes)s.') % {
                        'item': line.label, 'changes': ', '.join(changed)})
        return super().write(vals)
