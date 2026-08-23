# -*- coding: utf-8 -*-
import base64
from collections import Counter

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AirlogicServiceVisitFieldServiceExt(models.Model):
    """Adds the job-aware parts of Visit: the Service Jobs tab, invoicing
    (priced per unit per category, from the visit's jobs/equipment), and
    the Owner Report print/email actions. Field Service depends on
    Inventory, not the other way around, so this lives here rather than
    on the base airlogic.service.visit model.
    """
    _inherit = 'airlogic.service.visit'

    job_ids = fields.One2many('airlogic.service.job', 'visit_id', string='Service Jobs')
    job_count = fields.Integer(compute='_compute_job_count')

    @api.depends('job_ids')
    def _compute_job_count(self):
        for rec in self:
            rec.job_count = len(rec.job_ids)

    def _job_status(self, job):
        """Derived health status for one job's unit, from real checklist
        data (no separate status field to keep in sync by hand): a
        detected leak is urgent, any flagged/alert item is watch, else
        good.

        The leak checklist item never actually stores the literal string
        'leak' -- the mobile app writes 'pass' (no leak), '' (not yet
        assessed), or a comma-separated list of spot indices like "0,3"
        when a leak is marked (see mobile_app.js's leakDetected getter,
        toggleLeakSpot). Comparing against l.value == 'leak' here never
        matched anything, so leak detection silently never fired; fixed
        to check for "has a value, and it isn't 'pass'" instead, same
        test the mobile app itself uses. 'alert' items were also being
        ignored entirely (only 'flagged' counted) -- both now count.
        """
        lines = job.checklist_line_ids
        leak_line = lines.filtered(lambda l: l.key == 'leak')
        if leak_line.value and leak_line.value != 'pass':
            return 'urgent'
        if any(l.value in ('flagged', 'alert') for l in lines):
            return 'watch'
        return 'good'

    def _job_issues(self, job):
        """Every flagged/alert item, plus a detected leak, each carrying
        its technician-written note if there is one -- not just the
        item's label, so the Owner Report shows what was actually found,
        not just that something was.
        """
        issues = []
        for line in job.checklist_line_ids:
            if line.value in ('flagged', 'alert'):
                issues.append({
                    'label': line.label,
                    'severity': line.value,
                    'note': line.note or '',
                })
        leak_line = job.checklist_line_ids.filtered(lambda l: l.key == 'leak')
        if leak_line.value and leak_line.value != 'pass':
            issues.append({
                'label': _('Leak Detected'),
                'severity': 'flagged',
                'note': leak_line.note or '',
            })
        return issues

    def action_print_owner_report(self):
        self.ensure_one()
        report = self.env.ref('airlogic_field_service.action_report_airlogic_owner_report')
        return report.report_action(self)

    def action_send_report_email(self):
        self.ensure_one()
        report = self.env.ref('airlogic_field_service.action_report_airlogic_owner_report')
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
