# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .airlogic_checklist_line import CHECKLIST_ITEMS


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
    date = fields.Datetime(string='Visit Date', default=fields.Datetime.now, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
    ], string='Status', default='draft', tracking=True)
    notes = fields.Text(string='Tech Notes')
    reading_line_ids = fields.One2many(
        'airlogic.reading.line', 'job_id', string='Measurements')
    checklist_line_ids = fields.One2many(
        'airlogic.checklist.line', 'job_id', string='Visual Checklist')
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
            if not job.checklist_line_ids:
                job._populate_checklist_lines()
        return jobs

    def _populate_reading_lines(self):
        self.ensure_one()
        fields_active = self.env['airlogic.measurement.field'].search([])
        self.env['airlogic.reading.line'].create([
            {'job_id': self.id, 'field_id': f.id}
            for f in fields_active
        ])

    def _populate_checklist_lines(self):
        self.ensure_one()
        self.env['airlogic.checklist.line'].create([
            {'job_id': self.id, 'phase': phase, 'key': key, 'label': label}
            for phase, key, label in CHECKLIST_ITEMS
        ])

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_open_visual_checklist(self):
        """Launch the Ph1-4 visual-checklist OWL client action, pre-filled
        with any previously-saved values.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'airlogic_visual_checklist',
            'name': _('Visual Checklist'),
            'target': 'current',
            'params': {
                'job_id': self.id,
                'job_name': self.name,
                'equipment_name': self.equipment_id.display_name,
                'values': {l.key: l.value for l in self.checklist_line_ids if l.value},
            },
        }

    def action_save_visual_checklist(self, values):
        """Called by the OWL client action's Done button via the ORM
        service. values: dict of item key -> entered value.
        """
        self.ensure_one()
        lines_by_key = {line.key: line for line in self.checklist_line_ids}
        for key, val in (values or {}).items():
            line = lines_by_key.get(key)
            if line is not None:
                line.value = val
        return True

    def action_save_reading_lines(self, values):
        """Called from the mobile field-entry app. values: dict of
        measurement field code -> entered value.
        """
        self.ensure_one()
        lines_by_code = {line.field_id.code: line for line in self.reading_line_ids}
        for code, val in (values or {}).items():
            line = lines_by_code.get(code)
            if line is not None:
                line.value = val
        return True

    def get_field_entry_data(self):
        """Single-call data fetch for the mobile field-entry app, so it
        doesn't need several separate search_read round-trips per job.
        """
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'equipment_name': self.equipment_id.display_name,
            'has_pdf': bool(self.fp_pdf),
            'media_count': len(self.media_ids),
            'reading_lines': [{
                'code': line.field_id.code,
                'label': line.field_id.name,
                'section': line.section,
                'unit': line.unit,
                'standard': line.standard,
                'sequence': line.sequence,
                'value': line.value,
            } for line in self.reading_line_ids],
            'checklist_lines': [{
                'key': line.key,
                'label': line.label,
                'phase': line.phase,
                'value': line.value,
            } for line in self.checklist_line_ids],
        }

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
