# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicEquipment(models.Model):
    _name = 'airlogic.equipment'
    _description = 'Airlogic Equipment (Aircon Unit)'
    _order = 'partner_id, sublocation_id, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Unit Label', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True, tracking=True)
    sublocation_id = fields.Many2one(
        'airlogic.sublocation', string='Sublocation', tracking=True)
    serial_number = fields.Char(string='Serial Number')
    brand_id = fields.Many2one('airlogic.equipment.brand', string='Brand', tracking=True)
    model = fields.Char(string='Model', tracking=True, help='e.g. 40MBFQ12')
    hp_id = fields.Many2one('airlogic.equipment.hp', string='HP', tracking=True)
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
