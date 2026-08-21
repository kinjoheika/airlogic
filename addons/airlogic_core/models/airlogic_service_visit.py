# -*- coding: utf-8 -*-
from collections import Counter

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AirlogicServiceVisit(models.Model):
    """One site visit, covering one or more pieces of equipment (each a
    separate airlogic.service.job underneath). Pricing and invoicing live
    here, not on the job: priced per unit serviced per category, not per
    device, so one invoice line per category summarizes the whole visit.
    """
    _name = 'airlogic.service.visit'
    _description = 'Airlogic Service Visit'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', default='/', copy=False, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    technician_id = fields.Many2one(
        'res.users', string='Technician', default=lambda self: self.env.user, tracking=True)
    date = fields.Datetime(string='Visit Date', default=fields.Datetime.now, tracking=True)
    job_ids = fields.One2many('airlogic.service.job', 'visit_id', string='Service Jobs')
    job_count = fields.Integer(compute='_compute_job_count')
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', readonly=True, copy=False)

    @api.depends('job_ids')
    def _compute_job_count(self):
        for rec in self:
            rec.job_count = len(rec.job_ids)

    @api.model_create_multi
    def create(self, vals_list):
        visits = super().create(vals_list)
        for visit in visits:
            if visit.name == '/':
                visit.name = self.env['ir.sequence'].next_by_code('airlogic.service.visit') or '/'
        return visits

    def action_create_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return self._open_invoice()
        if not self.job_ids:
            raise UserError(_("Add at least one service job to this visit before invoicing."))
        counts = Counter()
        for job in self.job_ids:
            category = job.equipment_id.category_id
            if not category:
                raise UserError(_(
                    "Equipment %s has no category set -- set one under "
                    "Equipment before invoicing.") % job.equipment_id.display_name)
            counts[category] += 1
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'name': _('%(category)s service — %(visit)s') % {
                    'category': category.name, 'visit': self.name},
                'quantity': qty,
                'price_unit': category.rate,
            }) for category, qty in counts.items()],
        })
        self.invoice_id = move.id
        return self._open_invoice()

    def _open_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
        }
