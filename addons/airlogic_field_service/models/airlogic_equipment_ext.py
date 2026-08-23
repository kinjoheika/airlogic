# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .airlogic_checklist_line import CHECKLIST_ITEMS


class AirlogicEquipmentFieldServiceExt(models.Model):
    """Adds the job-aware parts of Equipment (Field Service depends on
    Inventory, not the other way around) -- stat button + the Reading/
    Visual Comparison tabs, all of which read airlogic.service.job data
    that only exists once this module is installed.
    """
    _inherit = 'airlogic.equipment'

    job_ids = fields.One2many('airlogic.service.job', 'equipment_id', string='Service Jobs')
    job_count = fields.Integer(compute='_compute_job_count')
    reading_comparison_html = fields.Html(
        string='Reading Comparison', compute='_compute_reading_comparison_html', sanitize=False)
    visual_comparison_html = fields.Html(
        string='Visual Comparison', compute='_compute_visual_comparison_html', sanitize=False)

    @api.depends('job_ids')
    def _compute_job_count(self):
        for rec in self:
            rec.job_count = len(rec.job_ids)

    def action_view_jobs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Service Jobs',
            'res_model': 'airlogic.service.job',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id},
        }

    def _last_3_jobs(self):
        self.ensure_one()
        return self.env['airlogic.service.job'].search(
            [('equipment_id', '=', self.id)], order='date desc', limit=3)

    def _job_header_parts(self, job):
        """Plain-text (when, technician) pair -- shared by the desktop
        HTML table (wrapped in markup by _format_job_header) and the
        mobile JSON endpoints (rendered natively in OWL, no HTML needed).
        """
        if job.date:
            local_dt = fields.Datetime.context_timestamp(self, job.date)
            when = local_dt.strftime('%b %d, %Y, %I:%M %p')
        else:
            when = job.name
        return when, job.technician_id.name

    def _format_job_header(self, job):
        """Date + time (in the viewing user's timezone) on one line,
        technician on a second, smaller line.
        """
        when, tech = self._job_header_parts(job)
        header = Markup('<div>%s</div>') % escape(when)
        if tech:
            header += Markup('<div class="text-muted" style="font-weight:400;">%s</div>') % escape(tech)
        return header

    @api.depends('job_ids.reading_line_ids.value')
    def _compute_reading_comparison_html(self):
        for equip in self:
            equip.reading_comparison_html = equip._build_reading_comparison_html()

    def _build_reading_comparison_html(self):
        self.ensure_one()
        jobs = self._last_3_jobs()
        if not jobs:
            return Markup('<p class="text-muted">No readings yet for this unit.</p>')

        headers = [self._format_job_header(job) for job in jobs]
        while len(headers) < 3:
            headers.append(Markup('—'))

        rows = []
        last_section = None
        for f in self.env['airlogic.measurement.field'].search([]):
            if f.section != last_section:
                rows.append(Markup(
                    '<tr class="table-light"><td colspan="5"><strong>%s</strong></td></tr>'
                ) % escape(f.section or ''))
                last_section = f.section
            cells = []
            for job in jobs:
                line = job.reading_line_ids.filtered(lambda l, f=f: l.field_id.id == f.id)
                value = line.value if line else False
                if value:
                    text = value + (f' {f.unit}' if f.unit else '')
                else:
                    text = '—'
                cells.append(Markup('<td>%s</td>') % escape(text))
            while len(cells) < 3:
                cells.append(Markup('<td>—</td>'))
            std = escape(f.standard) if f.standard else '—'
            rows.append(Markup('<tr><td>%s</td><td class="text-muted">%s</td>%s</tr>') % (
                escape(f.name), std, Markup('').join(cells)))

        header_cells = Markup('').join(
            Markup('<th>%s</th>') % h for h in headers)
        return Markup("""
            <table class="table table-sm table-bordered">
                <thead>
                    <tr>
                        <th>Field</th>
                        <th>Mfr. Standard</th>
                        %s
                    </tr>
                </thead>
                <tbody>%s</tbody>
            </table>
        """) % (header_cells, Markup('').join(rows))

    @api.depends('job_ids.checklist_line_ids.value')
    def _compute_visual_comparison_html(self):
        for equip in self:
            equip.visual_comparison_html = equip._build_visual_comparison_html()

    def _build_visual_comparison_html(self):
        self.ensure_one()
        jobs = self._last_3_jobs()
        if not jobs:
            return Markup('<p class="text-muted">No visual checklist entries yet for this unit.</p>')

        headers = [self._format_job_header(job) for job in jobs]
        while len(headers) < 3:
            headers.append(Markup('—'))

        rows = []
        last_phase = None
        for phase, key, label, _item_type, _unit in CHECKLIST_ITEMS:
            if phase != last_phase:
                rows.append(Markup(
                    '<tr class="table-light"><td colspan="4"><strong>Phase %s</strong></td></tr>'
                ) % phase)
                last_phase = phase
            cells = []
            for job in jobs:
                line = job.checklist_line_ids.filtered(lambda l, key=key: l.key == key)
                value = line.value if line else False
                cells.append(Markup('<td>%s</td>') % (escape(value) if value else '—'))
            while len(cells) < 3:
                cells.append(Markup('<td>—</td>'))
            rows.append(Markup('<tr><td>%s</td>%s</tr>') % (
                escape(label), Markup('').join(cells)))

        header_cells = Markup('').join(
            Markup('<th>%s</th>') % h for h in headers)
        return Markup("""
            <table class="table table-sm table-bordered">
                <thead>
                    <tr>
                        <th>Item</th>
                        %s
                    </tr>
                </thead>
                <tbody>%s</tbody>
            </table>
        """) % (header_cells, Markup('').join(rows))

    # --- Mobile-friendly comparison data -----------------------------
    # Same underlying data as the two HTML tables above, but as plain
    # JSON: the desktop table (Field / Standard / up to 3 job columns) is
    # far too wide for a phone screen, so the mobile Units tab renders
    # this as stacked cards instead of t-out-ing a wide <table>.

    def get_reading_comparison_data(self):
        self.ensure_one()
        jobs = self._last_3_jobs()
        job_headers = [
            {'when': when, 'technician': tech}
            for when, tech in (self._job_header_parts(j) for j in jobs)
        ]
        sections = []
        last_section = None
        section_fields = None
        for f in self.env['airlogic.measurement.field'].search([]):
            if f.section != last_section:
                section_fields = []
                sections.append({'section': f.section or '', 'fields': section_fields})
                last_section = f.section
            values = []
            for job in jobs:
                line = job.reading_line_ids.filtered(lambda l, f=f: l.field_id.id == f.id)
                value = line.value if line else False
                values.append((value + (' ' + f.unit if f.unit else '')) if value else '—')
            section_fields.append({'name': f.name, 'standard': f.standard or '', 'values': values})
        return {'job_headers': job_headers, 'sections': sections}

    def get_visual_comparison_data(self):
        self.ensure_one()
        jobs = self._last_3_jobs()
        job_headers = [
            {'when': when, 'technician': tech}
            for when, tech in (self._job_header_parts(j) for j in jobs)
        ]
        phases = []
        last_phase = None
        phase_items = None
        for phase, key, label, _item_type, _unit in CHECKLIST_ITEMS:
            if phase != last_phase:
                phase_items = []
                phases.append({'phase': phase, 'items': phase_items})
                last_phase = phase
            values = []
            notes = []
            for job in jobs:
                line = job.checklist_line_ids.filtered(lambda l, key=key: l.key == key)
                values.append(line.value if line and line.value else '—')
                notes.append(line.note if line else '')
            phase_items.append({'label': label, 'values': values, 'notes': notes})
        return {'job_headers': job_headers, 'phases': phases}

    # --- Senior Technician-gated Add/Delete (mobile app) ---------------
    # The mobile app's Add/Delete Equipment tab already requires the
    # Senior Technician PIN before it's even reachable, but a client-side
    # gate alone isn't real access control -- these re-check the same
    # role server-side (using the calling user's own session, not
    # spoofable) before the actual write, then sudo() past the base ACL
    # so a Senior Technician doesn't also need full Manager rights.
    # Regular technicians keep read/write-existing-fields access only
    # (see ir.model.access.csv); create/unlink go through here instead.

    @api.model
    def action_senior_tech_create(self, *args, **kwargs):
        """Takes *args instead of a plain `vals` param for the same reason
        as the res.users PIN RPCs (airlogic_res_users_ext.py): this
        build's call_kw arg-stripping for a zero/variable-arg @api.model
        method has been inconsistent.
        """
        vals = args[-1] if args else kwargs.get('vals')
        if not self.env.user.airlogic_is_senior_technician:
            raise AccessError(_("Only Senior Technicians can add equipment from the mobile app."))
        return self.sudo().create(vals)

    def action_senior_tech_write(self, vals):
        if not self.env.user.airlogic_is_senior_technician:
            raise AccessError(_("Only Senior Technicians can edit equipment from the mobile app."))
        return self.sudo().write(vals)

    def action_senior_tech_unlink(self):
        if not self.env.user.airlogic_is_senior_technician:
            raise AccessError(_("Only Senior Technicians can delete equipment from the mobile app."))
        # equipment_id on airlogic.service.job has no ondelete='cascade' on
        # purpose -- readings/checklist history are real business records
        # a Manager may still need, so a mistaken tap in the field can't
        # wipe them. "Delete" here is for correcting a duplicate/mistaken
        # entry, not for retiring a unit with real history (a Manager can
        # still do that deliberately from Inventory > Equipment).
        for equip in self:
            if equip.job_ids:
                raise UserError(_(
                    "Can't delete %(name)s -- it has %(count)d service job(s) on "
                    "record. A Manager can remove it from Inventory > Equipment "
                    "if it's really no longer in service.",
                    name=equip.display_name, count=len(equip.job_ids)))
        return self.sudo().unlink()
