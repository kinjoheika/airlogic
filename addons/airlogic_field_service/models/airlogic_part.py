# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError


def _create_purchase_rfq(request, product, qty, origin, note_target):
    """Shared by Part Request and Consumable Request approval (AIR-T60):
    a draft purchase.order (an RFQ, not yet confirmed) for the given
    product/qty, from its first configured vendor, with `user_id` set
    to whoever approved it (Operations Officer or Manager) -- Purchase
    Representative is the native purchase.order field for "who on our
    side owns this RFQ", so the approver's identity carries onto the
    actual purchase document, not just this app's own request record.
    If no vendor is set up yet, this just leaves a chatter note instead
    of raising -- a missing vendor shouldn't block the approval itself,
    just the automation on top of it.
    """
    supplierinfo = request.env['product.supplierinfo'].search(
        [('product_tmpl_id', '=', product.product_tmpl_id.id)],
        order='sequence, price', limit=1)
    if not supplierinfo:
        note_target.message_post(body=_(
            'Approved, but "%s" has no vendor configured yet (Purchase tab > '
            'Vendor Pricelist on the product) -- add one to enable automatic '
            'RFQ creation.') % product.display_name)
        return False
    po = request.env['purchase.order'].create({
        'partner_id': supplierinfo.partner_id.id,
        'user_id': request.env.user.id,
        'origin': origin,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_qty': qty,
            'price_unit': supplierinfo.price,
            'name': product.display_name,
        })],
    })
    po.message_post(body=_(
        'Created from %(origin)s, approved by %(approver)s.') % {
        'origin': origin, 'approver': request.env.user.name})
    note_target.message_post(body=_(
        '"%(part)s" approved by %(approver)s -- RFQ %(po)s created with %(vendor)s.') % {
        'part': product.display_name, 'approver': request.env.user.name,
        'po': po.name, 'vendor': supplierinfo.partner_id.display_name,
    })
    return po


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
    # Related, not a second Many2one to keep in sync by hand: the Job
    # already knows its own equipment, this just surfaces it here too
    # (AIR-T60) so a reviewer sees which unit a request is for, and so
    # this list/form can link straight to Equipment > Compatible Parts
    # for a second opinion on whether the requested part actually fits.
    equipment_id = fields.Many2one(
        'airlogic.equipment', related='job_id.equipment_id', string='Equipment', store=True)
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
             '(Purchase tab > Vendor Pricelist), with the approving Operations '
             'Officer/Manager set as its Purchase Representative. Left empty if the '
             'part has no vendor configured yet -- see the chatter for a note.')

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
            if not req.purchase_order_id:
                po = _create_purchase_rfq(req, req.part_id, 1, req.job_id.name, req.job_id)
                if po:
                    req.purchase_order_id = po.id

    def action_reject(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can reject a part request."))
        self.write({'state': 'rejected'})

    def action_fulfill(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can mark a part request fulfilled."))
        self.write({'state': 'fulfilled'})


class AirlogicConsumableRequest(models.Model):
    """Ordering generic field-service consumables (coil cleaner,
    insulation, copper tube, etc.) -- deliberately NOT tied to a
    specific job/unit the way a Part Request is, since these are
    supplies used across jobs, not a diagnosed replacement for one
    broken component.

    Now goes through the same Operations Officer/Manager approval gate
    as a Part Request (AIR-T60): the RFQ is only created on approval,
    not on the technician's own request, so both request types carry
    an approver's identity onto the resulting purchase document the
    same way.
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
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='requested', required=True, tracking=True)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase RFQ', readonly=True, copy=False)

    def action_approve(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can approve a consumable request."))
        self.write({'state': 'approved'})
        for req in self:
            if not req.purchase_order_id:
                origin = _('Consumable request by %s') % req.technician_id.name
                po = _create_purchase_rfq(req, req.product_id, req.quantity, origin, req)
                if po:
                    req.purchase_order_id = po.id

    def action_reject(self):
        if not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            raise AccessError(_("Only an Operations Officer or Manager can reject a consumable request."))
        self.write({'state': 'rejected'})
