# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AirlogicServiceVisit(models.Model):
    """One site visit to a client. Invoicing and the Owner Report are
    job-aware and live in the Field Service module's extension of this
    model (airlogic_field_service/models/airlogic_service_visit_ext.py),
    since Inventory has no knowledge of airlogic.service.job.
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
    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Review'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        visits = super().create(vals_list)
        for visit in visits:
            if visit.name == '/':
                visit.name = self.env['ir.sequence'].next_by_code('airlogic.service.visit') or '/'
        return visits

    def action_submit_for_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _report_filename(self):
        self.ensure_one()
        if self.date:
            date_str = fields.Datetime.context_timestamp(self, self.date).strftime('%Y-%m-%d')
        else:
            date_str = ''
        return 'StandardAir_Field Service Report_%s_%s' % (
            self.partner_id.name or 'Client', date_str)

    def _open_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
        }
