# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AirlogicServiceJob(models.Model):
    _name = 'airlogic.service.job'
    _description = 'Airlogic Service Job'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', default='/', copy=False, tracking=True)
    visit_id = fields.Many2one(
        'airlogic.service.visit', string='Visit', ondelete='set null', tracking=True)
    equipment_id = fields.Many2one(
        'airlogic.equipment', string='Equipment', required=True, tracking=True)
    partner_id = fields.Many2one(
        related='equipment_id.partner_id', string='Client', store=True, readonly=True)
    technician_id = fields.Many2one(
        'res.users', string='Technician', default=lambda self: self.env.user, tracking=True)
    date = fields.Date(string='Visit Date', default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
    ], string='Status', default='draft', tracking=True)
    notes = fields.Text(string='Tech Notes')
    reading_line_ids = fields.One2many(
        'airlogic.reading.line', 'job_id', string='Measurements')
    fp_pdf = fields.Binary(string='Fieldpiece PDF', attachment=True)
    fp_pdf_filename = fields.Char(string='Fieldpiece PDF Filename')
    media_ids = fields.Many2many(
        'ir.attachment', string='Photos / Videos',
        help='Job-site photos and videos. Stored as normal Odoo attachments '
             '-- if the filestore is later moved to object storage (e.g. '
             'Cloudflare R2), these move transparently with it.')

    @api.model_create_multi
    def create(self, vals_list):
        jobs = super().create(vals_list)
        for job in jobs:
            if job.name == '/':
                job.name = self.env['ir.sequence'].next_by_code('airlogic.service.job') or '/'
            if not job.reading_line_ids:
                job._populate_reading_lines()
        return jobs

    def _populate_reading_lines(self):
        self.ensure_one()
        fields_active = self.env['airlogic.measurement.field'].search([])
        self.env['airlogic.reading.line'].create([
            {'job_id': self.id, 'field_id': f.id}
            for f in fields_active
        ])

    def action_submit(self):
        self.write({'state': 'submitted'})

    @api.model
    def _extract_pdf_lines(self, pdf_bytes):
        """Return the PDF's text as a list of stripped, non-empty lines.
        Imported lazily (not at module load) so a missing pypdf on this
        Odoo instance can't crash the whole registry -- only this button.
        """
        try:
            import pypdf
        except ImportError:
            try:
                import PyPDF2 as pypdf
            except ImportError:
                raise UserError(_(
                    "No PDF library is available on this Odoo instance "
                    "(tried pypdf and PyPDF2). Ask your odoo.sh admin to "
                    "add 'pypdf' to the Python requirements."))
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() or '' for page in reader.pages)
        return [line.strip() for line in text.splitlines() if line.strip()]

    def action_import_fieldpiece_pdf(self):
        self.ensure_one()
        if not self.fp_pdf:
            raise UserError(_("Attach a Fieldpiece PDF report first."))
        lines = self._extract_pdf_lines(base64.b64decode(self.fp_pdf))
        filled = 0
        for line_rec in self.reading_line_ids:
            label = line_rec.field_id.pdf_label or line_rec.field_id.name
            for line in lines:
                if not line.startswith(label):
                    continue
                raw = line[len(label):].strip()
                if not raw or raw == '-':
                    break
                unit = line_rec.field_id.unit
                if unit and raw.endswith(unit):
                    raw = raw[:-len(unit)].strip()
                line_rec.value = raw
                filled += 1
                break
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fieldpiece PDF imported'),
                'message': _('%(filled)d of %(total)d fields filled from the PDF.') % {
                    'filled': filled, 'total': len(self.reading_line_ids)},
                'type': 'success' if filled else 'warning',
            },
        }
