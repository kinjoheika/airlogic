# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AirlogicEquipment(models.Model):
    _name = 'airlogic.equipment'
    _description = 'Airlogic Equipment (Aircon Unit)'
    _order = 'partner_id, sublocation, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Model', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True, tracking=True)
    sublocation = fields.Char(string='Sublocation', help='e.g. Rooftop Parking, 3rd Floor Server Room')
    serial_number = fields.Char(string='Serial Number')
    equipment_type = fields.Selection([
        ('split_wall', 'Split-Wall'),
        ('split_floor', 'Split-Floor'),
        ('window', 'Window Type'),
        ('other', 'Other'),
    ], string='Type', default='split_wall')
    install_year = fields.Integer(string='Install Year')
    active = fields.Boolean(default=True)
    job_ids = fields.One2many('airlogic.service.job', 'equipment_id', string='Service Jobs')
    job_count = fields.Integer(compute='_compute_job_count')

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
