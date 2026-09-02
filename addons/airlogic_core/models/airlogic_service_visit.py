# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError


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
        ('review', 'For Review'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', readonly=True, copy=False)
    reviewed_by_id = fields.Many2one(
        'res.users', string='Reviewed By', readonly=True, copy=False,
        help='Set automatically when a Manager approves this visit -- '
             'shown on the Owner Report and gates when the visit\'s jobs '
             'become visible in the mobile app\'s History tab.')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_technician_reassignment(vals_list)
        visits = super().create(vals_list)
        for visit in visits:
            if visit.name == '/':
                visit.name = self.env['ir.sequence'].next_by_code('airlogic.service.visit') or '/'
        return visits

    def write(self, vals):
        if 'technician_id' in vals:
            self._check_technician_reassignment([vals])
        return super().write(vals)

    def _check_technician_reassignment(self, vals_list):
        """Only Supervisor+ can assign/reassign a visit to a technician
        other than the acting user -- a plain Technician can still create
        or keep their own visits (technician_id defaults to self.env.user),
        just not hand one to, or take one from, someone else.
        """
        if self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            return
        for vals in vals_list:
            tech_id = vals.get('technician_id')
            if tech_id and tech_id != self.env.user.id:
                raise AccessError(_(
                    "Only an Operations Officer or Manager can assign or reassign "
                    "the technician on a Service Visit."))

    def action_submit_for_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved', 'reviewed_by_id': self.env.user.id})

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
