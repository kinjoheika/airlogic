# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMoveFieldServiceExt(models.Model):
    _inherit = 'account.move'

    airlogic_contract_id = fields.Many2one(
        'airlogic.service.contract', string='Subscription Contract', readonly=True, copy=False,
        help='Set when this invoice was generated automatically by a subscription '
             "contract's billing-period cron (see airlogic.service.contract).")
