# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AirlogicServiceJob(models.Model):
    _name = 'airlogic.service.job'
    _description = 'Airlogic Service Job'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', default='/', copy=False, tracking=True)
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
