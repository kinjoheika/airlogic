# -*- coding: utf-8 -*-
import base64
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
    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Review'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)
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

    def action_submit_for_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _job_status(self, job):
        """Derived health status for one job's unit, from real checklist
        data (no separate status field to keep in sync by hand):
        a detected leak is urgent, any flagged item is watch, else good.
        """
        lines = job.checklist_line_ids
        if any(l.key == 'leak' and l.value == 'leak' for l in lines):
            return 'urgent'
        if any(l.value == 'flagged' for l in lines):
            return 'watch'
        return 'good'

    def _job_issues(self, job):
        issues = []
        for line in job.checklist_line_ids:
            if line.value == 'flagged':
                issues.append(line.label)
            elif line.key == 'leak' and line.value == 'leak':
                issues.append(_('%s — Leak detected') % line.label)
        return issues

    def _report_filename(self):
        self.ensure_one()
        if self.date:
            date_str = fields.Datetime.context_timestamp(self, self.date).strftime('%Y-%m-%d')
        else:
            date_str = ''
        return 'StandardAir_Field Service Report_%s_%s' % (
            self.partner_id.name or 'Client', date_str)

    def action_print_owner_report(self):
        self.ensure_one()
        return self.env.ref('airlogic_core.action_report_airlogic_owner_report').report_action(self)

    def action_send_report_email(self):
        self.ensure_one()
        report = self.env.ref('airlogic_core.action_report_airlogic_owner_report')
        pdf_content, _fmt = report._render_qweb_pdf(report.report_name, self.ids)
        attachment = self.env['ir.attachment'].create({
            'name': '%s.pdf' % self._report_filename(),
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Report'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'airlogic.service.visit',
                'default_res_ids': [self.id],
                'default_partner_ids': [self.partner_id.id] if self.partner_id else [],
                'default_subject': self._report_filename(),
                'default_attachment_ids': [(4, attachment.id)],
                'default_composition_mode': 'comment',
            },
        }

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
