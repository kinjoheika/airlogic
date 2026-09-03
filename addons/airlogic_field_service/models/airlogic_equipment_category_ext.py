# -*- coding: utf-8 -*-
from odoo import fields, models


class AirlogicEquipmentCategoryFieldServiceExt(models.Model):
    """Reverse side of product.template.airlogic_equipment_category_ids
    (AIR-T60): same relation table, so this is genuinely the same
    link, editable from either the part's form (Configuration >
    Requestable Parts) or straight from the category's own list
    (Configuration > Equipment Categories) -- whichever a Manager
    happens to be looking at when they think to set it up.
    """
    _inherit = 'airlogic.equipment.category'

    compatible_part_tmpl_ids = fields.Many2many(
        'product.template', relation='airlogic_part_category_rel',
        column1='category_id', column2='product_tmpl_id', string='Compatible Parts')
