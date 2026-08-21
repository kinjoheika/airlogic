# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models


class AirlogicEquipment(models.Model):
    _name = 'airlogic.equipment'
    _description = 'Airlogic Equipment (Aircon Unit)'
    _order = 'partner_id, sublocation, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Unit Label', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True, tracking=True)
    sublocation = fields.Char(string='Sublocation', help='e.g. Rooftop Parking, 3rd Floor Server Room')
    serial_number = fields.Char(string='Serial Number')
    brand = fields.Char(string='Brand', tracking=True, help='e.g. Carrier, Panasonic, Koppel')
    model = fields.Char(string='Model', tracking=True, help='e.g. 40MBFQ12')
    hp = fields.Float(string='HP', tracking=True, help='Capacity rating in horsepower')
    category_id = fields.Many2one(
        'airlogic.equipment.category', string='Category', required=True,
        help='Drives per-unit service pricing on invoices.')
    qty = fields.Integer(
        string='Qty', default=1,
        help='Number of identical units this record represents on the '
             'Parts Reference sheet.')
    ipm_model = fields.Char(string='IPM Model No.')
    pcb_model = fields.Char(string='PCB Model No.')
    capacitor_brand = fields.Char(string='Capacitor Brand')
    capacitor_uf = fields.Float(string='Capacitor µF')
    capacitor_volt = fields.Float(string='Capacitor V')
    refrigerant = fields.Char(string='Refrigerant', help='Specified refrigerant type, e.g. R-410A')
    compressor_brand = fields.Char(string='Compressor Brand')
    compressor_details = fields.Char(string='Compressor Details')
    install_year = fields.Integer(string='Install Year')
    active = fields.Boolean(default=True)
    job_ids = fields.One2many('airlogic.service.job', 'equipment_id', string='Service Jobs')
    job_count = fields.Integer(compute='_compute_job_count')
    reading_comparison_html = fields.Html(
        string='Reading Comparison', compute='_compute_reading_comparison_html', sanitize=False)

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

    @api.depends('job_ids.reading_line_ids.value')
    def _compute_reading_comparison_html(self):
        for equip in self:
            equip.reading_comparison_html = equip._build_reading_comparison_html()

    def _build_reading_comparison_html(self):
        self.ensure_one()
        jobs = self.env['airlogic.service.job'].search(
            [('equipment_id', '=', self.id)], order='date desc', limit=3)
        if not jobs:
            return Markup('<p class="text-muted">No readings yet for this unit.</p>')

        headers = [job.date.strftime('%b %d, %Y') if job.date else job.name for job in jobs]
        while len(headers) < 3:
            headers.append('—')

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
            rows.append(Markup('<tr><td>%s</td>%s<td class="text-muted">%s</td></tr>') % (
                escape(f.name), Markup('').join(cells), std))

        header_cells = Markup('').join(
            Markup('<th>%s</th>') % escape(h) for h in headers)
        return Markup("""
            <table class="table table-sm table-bordered">
                <thead>
                    <tr>
                        <th>Field</th>
                        %s
                        <th>Mfr. Standard</th>
                    </tr>
                </thead>
                <tbody>%s</tbody>
            </table>
        """) % (header_cells, Markup('').join(rows))
