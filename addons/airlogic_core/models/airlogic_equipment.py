# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicEquipment(models.Model):
    _name = 'airlogic.equipment'
    _description = 'Airlogic Equipment (Aircon Unit)'
    _order = 'partner_id, sublocation_id, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Unit Label', required=True, tracking=True,
        help='A proper name for this one specific device (e.g. "AC Unit 1 '
             '- Server Room"), not a generic type/category label -- each '
             'record is one physical unit, not a bucket of identical ones.')
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True, tracking=True)
    sublocation_id = fields.Many2one(
        'airlogic.sublocation', string='Sublocation', tracking=True,
        help='The one specific spot this specific unit is installed in. '
             'One sublocation holds exactly one piece of equipment -- if a '
             'room genuinely has multiple units, give each its own, more '
             'specific Sublocation (e.g. "Server Room - Unit 1" / "- Unit '
             '2") rather than reusing one for several.')
    serial_number = fields.Char(string='Serial Number')
    brand_id = fields.Many2one('airlogic.equipment.brand', string='Brand', tracking=True)
    model = fields.Char(string='Model', tracking=True, help='e.g. 40MBFQ12')
    hp_id = fields.Many2one('airlogic.equipment.hp', string='HP', tracking=True)
    category_id = fields.Many2one(
        'airlogic.equipment.category', string='Category', required=True,
        help='Drives per-unit service pricing on invoices.')
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

    # Client + Sublocation is one-to-one: a sublocation is one specific
    # device's spot, not a zone that can hold several. Postgres treats
    # NULL as distinct from any other NULL, so records with no
    # sublocation set yet aren't caught by this -- intentional, since
    # sublocation isn't required at the DB level (see the form view's
    # required="1", which only applies going forward and doesn't risk a
    # migration failure against any pre-existing rows).
    _partner_sublocation_unique = models.Constraint(
        'UNIQUE(partner_id, sublocation_id)',
        'This sublocation already has a piece of equipment. Each '
        'sublocation is one specific device\'s spot -- create a new, more '
        'specific Sublocation for this unit instead of reusing one.',
    )
