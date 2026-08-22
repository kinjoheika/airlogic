# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class AirlogicPart(models.Model):
    """Requestable-part catalog for the mobile app's Request Parts
    checklist. Deliberately name-only (no cost/stock fields) -- this is
    a tick list of what a technician noticed is needed, tied to a job
    for a Supervisor to review, not a real stock.quant/product
    consumption ledger. That's a materially bigger integration (the
    'stock' app isn't even a dependency here) than what was asked for.
    """
    _name = 'airlogic.part'
    _description = 'Airlogic Requestable Part'
    _order = 'zone, sequence, name'

    name = fields.Char(required=True)
    zone = fields.Selection([
        ('outdoor', 'Outdoor (Power OFF)'),
        ('indoor', 'Indoor'),
    ], required=True, help='Which DSR phase\'s Request Parts list this shows up in -- '
                            'Outdoor on Phase 2, Indoor on Phase 3. Phase 4 shows both.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class AirlogicPartRequest(models.Model):
    """One technician ticking one part as needed for one job. Approval
    is Supervisor+ only; there's no auto-approve threshold here since
    the source spec left the peso threshold as an open/unconfirmed item
    -- every request goes through the same review instead of guessing
    at a number nobody gave.
    """
    _name = 'airlogic.part.request'
    _description = 'Airlogic Part Request'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    job_id = fields.Many2one(
        'airlogic.service.job', string='Job', required=True, ondelete='cascade', tracking=True)
    part_id = fields.Many2one('airlogic.part', string='Part', required=True, tracking=True)
    requested_by = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True, tracking=True)
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('fulfilled', 'Fulfilled'),
        ('rejected', 'Rejected'),
    ], default='requested', tracking=True)

    _job_part_unique = models.Constraint(
        'UNIQUE(job_id, part_id)', 'This part is already requested for this job.')

    def unlink(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            for req in self:
                if req.state != 'requested':
                    raise AccessError(_(
                        "Only a Supervisor or Manager can remove a part request "
                        "that's already been reviewed."))
        return super().unlink()

    def action_approve(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only a Supervisor or Manager can approve a part request."))
        self.write({'state': 'approved'})

    def action_reject(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only a Supervisor or Manager can reject a part request."))
        self.write({'state': 'rejected'})

    def action_fulfill(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only a Supervisor or Manager can mark a part request fulfilled."))
        self.write({'state': 'fulfilled'})
