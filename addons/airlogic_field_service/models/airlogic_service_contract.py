# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class AirlogicServiceContract(models.Model):
    """Subscription / maintenance-plan layer (AIR-T54/Phase 6.4): a
    client on a contract gets a new Service Visit (covering its units,
    each with its own Service Job) and a recurring invoice generated
    automatically every billing period, via the cron below.

    Deliberately its own model rather than a deep integration with
    Odoo's native Subscriptions app (recurring Sales Orders): that
    app's exact field/model shape has shifted across Odoo versions and
    can't be verified without a live instance, so getting it wrong
    risks breaking module install entirely (the same class of failure
    as AIR-T41's sandboxed-import registry crash), not just a
    misbehaving feature. This model owns the recurring-visit and
    recurring-invoice mechanics outright -- fields and behavior fully
    in this addon's control -- while still billing period-triggered as
    asked, not on Visit approval or a generic nightly batch.
    """
    _name = 'airlogic.service.contract'
    _description = 'Airlogic Subscription / Maintenance Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'partner_id, id'

    _MONTHS_BY_PERIOD = {'monthly': 1, 'quarterly': 3, 'semi_annual': 6, 'annual': 12}

    name = fields.Char(default='/', copy=False, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    equipment_ids = fields.Many2many(
        'airlogic.equipment', string='Units Covered',
        domain="[('partner_id', '=', partner_id)]",
        help='Leave empty to cover every unit currently on file for this client '
             'at the time each period generates -- lets the contract track a '
             'growing fleet automatically instead of needing a manual update '
             'every time a unit is added.')
    billing_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ], default='quarterly', required=True, tracking=True)
    price = fields.Monetary(string='Price per Period', required=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    start_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    next_billing_date = fields.Date(
        tracking=True,
        help='Set on activation; advances by one Billing Period every time this '
             'contract generates its next visit + invoice. The daily cron '
             '(Airlogic: Generate Due Subscription Periods) picks up any '
             'contract whose date has arrived.')
    visit_ids = fields.One2many('airlogic.service.visit', 'contract_id', string='Generated Visits')
    visit_count = fields.Integer(compute='_compute_counts')
    invoice_ids = fields.One2many('account.move', 'airlogic_contract_id', string='Invoices')
    invoice_count = fields.Integer(compute='_compute_counts')

    @api.depends('visit_ids', 'invoice_ids')
    def _compute_counts(self):
        for c in self:
            c.visit_count = len(c.visit_ids)
            c.invoice_count = len(c.invoice_ids)

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        for c in contracts:
            if c.name == '/':
                c.name = self.env['ir.sequence'].next_by_code('airlogic.service.contract') or '/'
        return contracts

    def action_view_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visits'),
            'res_model': 'airlogic.service.visit',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('airlogic_contract_id', '=', self.id)],
        }

    def action_activate(self):
        for c in self:
            c.write({'state': 'active', 'next_billing_date': c.next_billing_date or c.start_date})

    def action_pause(self):
        self.write({'state': 'paused'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'next_billing_date': False})

    @api.model
    def _cron_generate_due_periods(self):
        """Called daily by ir.cron. Only picks up contracts whose
        next_billing_date has actually arrived -- the billing-period
        trigger the user asked for, not Visit-approval or a blanket
        nightly run touching every contract regardless of when it's due.
        """
        today = fields.Date.context_today(self)
        due = self.search([('state', '=', 'active'), ('next_billing_date', '<=', today)])
        due.action_generate_period()

    def action_generate_period(self):
        for contract in self:
            units = contract.equipment_ids or self.env['airlogic.equipment'].search(
                [('partner_id', '=', contract.partner_id.id)])
            visit = self.env['airlogic.service.visit'].create({
                'partner_id': contract.partner_id.id,
                'contract_id': contract.id,
            })
            for unit in units:
                self.env['airlogic.service.job'].create({
                    'equipment_id': unit.id,
                    'visit_id': visit.id,
                })
            self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': contract.partner_id.id,
                'invoice_origin': contract.name,
                'airlogic_contract_id': contract.id,
                'invoice_line_ids': [(0, 0, {
                    'name': _('%(period)s subscription — %(contract)s (%(visit)s)') % {
                        'period': dict(contract._fields['billing_period'].selection).get(
                            contract.billing_period),
                        'contract': contract.name,
                        'visit': visit.name,
                    },
                    'quantity': 1,
                    'price_unit': contract.price,
                })],
            })
            months = self._MONTHS_BY_PERIOD[contract.billing_period]
            contract.next_billing_date = contract.next_billing_date + relativedelta(months=months)
