# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class AirlogicPartRequest(models.Model):
    """One technician flagging a real product.product part as needed for
    one job. Approval is Operations Officer+ only; there's no auto-
    approve threshold here since the source spec left the peso
    threshold as an open/unconfirmed item -- every request goes through
    the same review instead of guessing at a number nobody gave.

    part_id used to point at the bespoke airlogic.part (name + zone
    only); it now points at a real product.product (AIR-T53/Phase 6.2)
    so approving a request can create an actual Purchase RFQ using that
    product's vendor pricing (product.supplierinfo), not just a tick on
    a checklist a Manager reads later.
    """
    _name = 'airlogic.part.request'
    _description = 'Airlogic Part Request'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    job_id = fields.Many2one(
        'airlogic.service.job', string='Job', required=True, ondelete='cascade', tracking=True)
    part_id = fields.Many2one('product.product', string='Part', required=True, tracking=True)
    requested_by = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True, tracking=True)
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('fulfilled', 'Fulfilled'),
        ('rejected', 'Rejected'),
    ], default='requested', tracking=True)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase RFQ', readonly=True, copy=False,
        help='Created automatically on approval, using the part\'s configured vendor '
             '(Purchase tab > Vendor Pricelist). Left empty if the part has no vendor '
             'configured yet -- see the chatter for a note when that happens.')

    _job_part_unique = models.Constraint(
        'UNIQUE(job_id, part_id)', 'This part is already requested for this job.')

    def unlink(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            for req in self:
                if req.state != 'requested':
                    raise AccessError(_(
                        "Only an Operations Officer or Manager can remove a part request "
                        "that's already been reviewed."))
        return super().unlink()

    def action_approve(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can approve a part request."))
        self.write({'state': 'approved'})
        for req in self:
            req._create_purchase_rfq()

    def action_reject(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can reject a part request."))
        self.write({'state': 'rejected'})

    def action_fulfill(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can mark a part request fulfilled."))
        self.write({'state': 'fulfilled'})

    def _create_purchase_rfq(self):
        """Draft purchase.order (an RFQ, not yet confirmed) for one unit
        of this part, from its first configured vendor. If no vendor is
        set up yet, this just leaves a chatter note instead of raising --
        a missing vendor shouldn't block the approval itself, just the
        automation on top of it.
        """
        self.ensure_one()
        if self.purchase_order_id:
            return
        supplierinfo = self.env['product.supplierinfo'].search(
            [('product_tmpl_id', '=', self.part_id.product_tmpl_id.id)],
            order='sequence, price', limit=1)
        if not supplierinfo:
            self.job_id.message_post(body=_(
                'Part Request approved for "%s", but it has no vendor configured yet '
                '(Purchase tab > Vendor Pricelist on the product) -- add one to enable '
                'automatic RFQ creation.') % self.part_id.display_name)
            return
        po = self.env['purchase.order'].create({
            'partner_id': supplierinfo.partner_id.id,
            'origin': self.job_id.name,
            'order_line': [(0, 0, {
                'product_id': self.part_id.id,
                'product_qty': 1,
                'price_unit': supplierinfo.price,
                'name': self.part_id.display_name,
            })],
        })
        self.purchase_order_id = po.id
        self.job_id.message_post(body=_(
            'Part Request for "%(part)s" approved -- RFQ %(po)s created with %(vendor)s.') % {
            'part': self.part_id.display_name,
            'po': po.name,
            'vendor': supplierinfo.partner_id.display_name,
        })


class AirlogicConsumableRequest(models.Model):
    """Ordering generic field-service consumables (coil cleaner,
    insulation, copper tube, etc.) -- deliberately NOT tied to a
    specific job/unit the way a Part Request is, since these are
    supplies used across jobs, not a diagnosed replacement for one
    broken component. No approval gate either: unlike a Part Request
    (which corrects/replaces something on a client's equipment and
    needs a second set of eyes), restocking routine supplies is a
    day-to-day technician call, so the RFQ is created immediately.
    """
    _name = 'airlogic.consumable.request'
    _description = 'Airlogic Consumable Request'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    technician_id = fields.Many2one(
        'res.users', string='Requested By', default=lambda self: self.env.user,
        readonly=True, tracking=True)
    product_id = fields.Many2one(
        'product.product', string='Consumable', required=True, tracking=True,
        domain=[('airlogic_is_consumable', '=', True)])
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase RFQ', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        for req in requests:
            req._create_purchase_rfq()
        return requests

    def _create_purchase_rfq(self):
        self.ensure_one()
        if self.purchase_order_id:
            return
        supplierinfo = self.env['product.supplierinfo'].search(
            [('product_tmpl_id', '=', self.product_id.product_tmpl_id.id)],
            order='sequence, price', limit=1)
        if not supplierinfo:
            self.message_post(body=_(
                'No vendor configured yet for "%s" -- add one under the product\'s '
                'Purchase tab to enable automatic RFQ creation.') % self.product_id.display_name)
            return
        po = self.env['purchase.order'].create({
            'partner_id': supplierinfo.partner_id.id,
            'origin': _('Consumable request by %s') % self.technician_id.name,
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'product_qty': self.quantity,
                'price_unit': supplierinfo.price,
                'name': self.product_id.display_name,
            })],
        })
        self.purchase_order_id = po.id
