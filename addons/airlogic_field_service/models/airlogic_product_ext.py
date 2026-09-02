# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplateFieldServiceExt(models.Model):
    """Parts catalog rebuild (AIR-T53/Phase 6.2): airlogic.part (name +
    zone only) is retired in favor of real product.template records, so
    Purchase's own vendor pricing (product.supplierinfo) is available
    and a Part Request can turn into a real RFQ on approval (see
    airlogic.part.request.action_approve).
    """
    _inherit = 'product.template'

    airlogic_requestable = fields.Boolean(
        string='Requestable in Field Service',
        help='Shown in the mobile app\'s Request Parts checklist (Configuration > '
             'Requestable Parts is this list, filtered).')
    airlogic_zone = fields.Selection([
        ('outdoor', 'Outdoor (Power OFF)'),
        ('indoor', 'Indoor'),
        ('both', 'Both / Either'),
    ], string='Field Service Zone',
        help='Which DSR phase\'s Request Parts list this shows up in -- Outdoor on '
             'Phase 2, Indoor on Phase 3, Both on Phase 4.')
    airlogic_is_consumable = fields.Boolean(
        string='Field Service Consumable',
        help='Shown in the mobile app\'s separate Order Consumables screen instead '
             'of the per-unit Request Parts list -- coil cleaner, insulation, copper '
             'tube, and other supplies used across jobs rather than swapped into one '
             'specific broken unit.')
    airlogic_equipment_category_ids = fields.Many2many(
        'airlogic.equipment.category', string='Compatible Equipment Categories',
        help='Which equipment categories this part fits. Powers the mobile app\'s '
             'Request Parts pre-fill: tapping Request Parts on a specific unit shows '
             'parts mapped to that unit\'s category first, so the technician confirms '
             'a part instead of typing/photographing it. Falls back to the full '
             'zone-filtered catalog if nothing is mapped yet for that category.')
