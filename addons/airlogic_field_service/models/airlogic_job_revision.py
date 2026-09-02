# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AirlogicJobRevision(models.Model):
    """Permanent record of a post-submission correction: old value, new
    value, and a mandatory reason, requested by a technician and applied
    only once a Supervisor+ approves it. Never edited or deleted after
    the fact -- this IS the audit trail the spec's diagnostic-integrity
    pitch depends on, so both the request and its outcome stay visible
    forever, whether approved or rejected.
    """
    _name = 'airlogic.job.revision'
    _description = 'Airlogic Job Revision Request'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    job_id = fields.Many2one(
        'airlogic.service.job', string='Job', required=True, ondelete='cascade', tracking=True)
    line_model = fields.Selection([
        ('reading', 'Measurement Reading'),
        ('checklist', 'Visual Checklist'),
    ], required=True, tracking=True)
    field_label = fields.Char(
        string='Item', required=True,
        help='Which item this correction is for, e.g. "Suction Line '
             'Pressure" or "Compressor Body" -- for humans reading the '
             'request; line_key below is what actually gets updated.')
    line_key = fields.Char(
        string='Field Code / Checklist Key', required=True,
        help='For a Measurement Reading: the Measurement Field\'s Code '
             '(Configuration > Measurement Fields). For a Visual '
             'Checklist item: its key, e.g. "coil" or "meg_u".')
    old_value = fields.Char(required=True)
    new_value = fields.Char(required=True)
    reason = fields.Text(required=True)
    requested_by = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True, tracking=True)
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='requested', tracking=True)

    def _find_line(self):
        self.ensure_one()
        if self.line_model == 'reading':
            return self.job_id.reading_line_ids.filtered(
                lambda l: l.field_id.code == self.line_key)
        return self.job_id.checklist_line_ids.filtered(lambda l: l.key == self.line_key)

    def action_approve(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can approve a revision."))
        for rev in self:
            if rev.state != 'requested':
                continue
            if rev.requested_by.id == self.env.user.id:
                raise UserError(_("You can't approve your own revision request."))
            line = rev._find_line()
            if not line:
                raise UserError(_(
                    "Can't find \"%s\" (code/key \"%s\") on this job anymore -- "
                    "nothing to apply the correction to.") % (rev.field_label, rev.line_key))
            # revision_open briefly lifts the submitted-job write lock
            # (see airlogic_ir_rule.xml's rule_reading_line_lock_submitted /
            # rule_checklist_line_lock_submitted) for exactly this write,
            # then closes it again -- the lock is global (applies to
            # everyone, including Supervisor+), so even the approval path
            # has to go through the same door instead of a raw bypass.
            rev.job_id.revision_open = True
            line.value = rev.new_value
            rev.job_id.revision_open = False
            rev.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_reject(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can reject a revision."))
        for rev in self:
            if rev.state == 'requested':
                rev.write({'state': 'rejected', 'approved_by': self.env.user.id})
