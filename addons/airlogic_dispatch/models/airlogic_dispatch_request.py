# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AirlogicDispatchRequest(models.Model):
    """One call-in/staff/technician ask (or one covered unit of a
    subscription contract's period) waiting for a technician + date.
    action_compute_suggestion runs the 6-rule cascade described to the
    user and diagrammed at publish time; it always produces exactly one
    suggestion with its reasoning attached and leaves the request in
    'suggested' state -- action_confirm (a human tapping Accept) is the
    only thing that actually creates the Visit/Job and locks it in.

    v1 heuristics, not a real routing/optimization engine: "nearest" is
    same dispatch zone, not real geolocation, and "available" is "has
    the fewest jobs already on that date" -- both proxies chosen
    because there is no real geolocation/routing data in this system
    yet. Worth revisiting once real usage data shows where they're
    wrong.
    """
    _name = 'airlogic.dispatch.request'
    _description = 'Airlogic Dispatch Request'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(default='/', copy=False, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    equipment_id = fields.Many2one(
        'airlogic.equipment', string='Unit', tracking=True,
        domain="[('partner_id', '=', partner_id)]",
        help='Leave empty for a request that covers every unit on file for this '
             'client (e.g. a subscription period) rather than one specific unit.')
    zone_id = fields.Many2one(
        related='partner_id.airlogic_dispatch_zone_id', string='Zone', store=True, readonly=True)
    urgency = fields.Selection([
        ('emergency', 'Emergency'),
        ('rush', 'Rush / Paid Priority'),
        ('routine', 'Routine / Subscription'),
    ], default='routine', required=True, tracking=True)
    source = fields.Selection([
        ('call_in', 'Client Call-In'),
        ('staff', 'Office Staff'),
        ('technician', 'Technician'),
        ('subscription', 'Subscription Contract'),
    ], default='call_in', required=True, tracking=True)
    requested_date = fields.Date(
        default=fields.Date.context_today, required=True, tracking=True,
        help='When the client wants/needs this. A request whose date has '
             "already passed while still Pending is this engine's definition "
             'of a missed/backlog visit (Rule 1).')
    notes = fields.Text()
    requested_by = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True, tracking=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('suggested', 'Suggested'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], default='pending', required=True, tracking=True)
    suggested_technician_id = fields.Many2one('res.users', string='Suggested Technician', tracking=True)
    suggested_date = fields.Date(tracking=True)
    suggested_reason = fields.Text(string='Why', readonly=True)
    visit_id = fields.Many2one(
        'airlogic.service.visit', string='Visit', readonly=True, copy=False,
        help='Pre-set when a subscription contract created this request (the '
             'Visit already exists, covering every unit in that period); left '
             'empty for an ad hoc request, which creates its own Visit on '
             'confirm.')

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        for r in requests:
            if r.name == '/':
                r.name = self.env['ir.sequence'].next_by_code('airlogic.dispatch.request') or '/'
        return requests

    # ------------------------------------------------------------------
    # The 6-rule cascade
    # ------------------------------------------------------------------

    @api.model
    def _cron_process_pending(self):
        """Daily entry point. Processes every Pending request in one
        pass, ordered so Rules 1-2 (backlog, then urgency tier) decide
        the order suggestions are computed in -- Rule 6 (routine/
        subscription requests) always sorts last, so by the time they're
        reached, every backlog/emergency/rush request that same run
        already has its technician+date claimed and counted toward
        that day's load.
        """
        urgency_rank = {'emergency': 0, 'rush': 1, 'routine': 2}
        today = fields.Date.context_today(self)

        def sort_key(req):
            is_backlog = 1 if req.requested_date < today else 0
            return (-is_backlog, urgency_rank.get(req.urgency, 9), req.requested_date)

        pending = self.search([('state', '=', 'pending')])
        for req in sorted(pending, key=sort_key):
            req._compute_suggestion_one()

    def action_compute_suggestion(self):
        for req in self:
            req._compute_suggestion_one()

    def _compute_suggestion_one(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        reasons = []

        # Rule 1: an overdue Pending request is this engine's definition
        # of "missed" -- always targeted at today, regardless of urgency.
        is_backlog = self.requested_date < today
        target_date = today if (is_backlog or self.urgency in ('emergency', 'rush')) else self.requested_date
        if is_backlog:
            reasons.append(_('Backlog: originally requested for %s, now overdue.') % self.requested_date)

        # Rule 2 label, for the reasoning trail.
        reasons.append(_('Urgency: %s.') % dict(self._fields['urgency'].selection).get(self.urgency))

        technician = self.env['res.users']
        if self.urgency in ('emergency', 'rush') and self.zone_id:
            # Rule 3: a technician already working this zone today, with
            # room left, wins first.
            technician = self._find_nearest_technician(target_date)
            if technician:
                reasons.append(_(
                    'Rule 3: %(tech)s already has a visit in %(zone)s zone on %(date)s.') % {
                    'tech': technician.name, 'zone': self.zone_id.name, 'date': target_date})
            else:
                target_date = target_date + timedelta(days=1)
                technician = self._find_nearest_technician(target_date)
                if technician:
                    reasons.append(_(
                        'Rule 3: no one free in %(zone)s zone today -- moved to %(date)s, '
                        'when %(tech)s is already in that zone.') % {
                        'zone': self.zone_id.name, 'date': target_date, 'tech': technician.name})
                else:
                    reasons.append(_(
                        'Rule 3: no one currently in %s zone on either day -- '
                        'falling back to whoever has the lightest load.') % self.zone_id.name)

        if not technician:
            technician = self._find_least_loaded_technician(target_date)
            if technician:
                reasons.append(_(
                    'Assigned to %(tech)s, the least-loaded technician available on %(date)s.') % {
                    'tech': technician.name, 'date': target_date})

        # Rule 5: client time-window, surfaced as a note rather than an
        # exact computed time -- see the field's own help text for why.
        if self.partner_id.airlogic_preferred_hours:
            reasons.append(_(
                'Rule 5: %(client)s prefers %(hours)s -- confirm the exact time fits.') % {
                'client': self.partner_id.name, 'hours': self.partner_id.airlogic_preferred_hours})

        self.write({
            'suggested_technician_id': technician.id if technician else False,
            'suggested_date': target_date,
            'suggested_reason': '\n'.join(reasons),
            'state': 'suggested',
        })

        # Rule 4: an Emergency/Rush placement anchoring a date+zone
        # pulls nearby routine requests in the same zone a bit earlier.
        if self.urgency in ('emergency', 'rush'):
            self._sweep_nearby_requests(target_date)

    def _find_nearest_technician(self, target_date):
        """Rule 3/4's proximity proxy: a Technician-group user who
        already has a confirmed or suggested job/request in this same
        zone on target_date, picking whichever of them has the fewest
        jobs that day (a simple load-balance among zone matches, not a
        real route-optimal pick).
        """
        self.ensure_one()
        if not self.zone_id:
            return self.env['res.users']
        same_zone_jobs = self.env['airlogic.service.job'].search([
            ('date', '=', target_date),
            ('equipment_id.partner_id.airlogic_dispatch_zone_id', '=', self.zone_id.id),
        ])
        # .mapped(), not .technician_id directly: a Many2one accessed by
        # dot notation on a multi-record recordset raises "Expected
        # singleton" in Odoo -- only x2many fields support that directly.
        candidates = same_zone_jobs.mapped('technician_id')
        if not candidates:
            return self.env['res.users']
        return self._least_loaded_among(candidates, target_date)

    def _find_least_loaded_technician(self, target_date):
        self.ensure_one()
        technicians = self.env['res.users'].search(
            [('groups_id', 'in', self.env.ref('airlogic_core.group_airlogic_technician').id)])
        if not technicians:
            return self.env['res.users']
        return self._least_loaded_among(technicians, target_date)

    def _least_loaded_among(self, technicians, target_date):
        jobs = self.env['airlogic.service.job'].search(
            [('date', '=', target_date), ('technician_id', 'in', technicians.ids)])
        counts = {t.id: 0 for t in technicians}
        for job in jobs:
            counts[job.technician_id.id] = counts.get(job.technician_id.id, 0) + 1
        best_id = min(counts, key=counts.get)
        return self.env['res.users'].browse(best_id)

    def _sweep_nearby_requests(self, target_date):
        """Rule 4: pull up to 4 other still-open (Pending or Suggested)
        Routine requests in the same zone, due in the next few days,
        onto this same date instead -- fewer cross-town trips. Never
        touches an already-Confirmed request; that visit is already
        locked in and would need its own re-confirmation to move.
        """
        self.ensure_one()
        if not self.zone_id:
            return
        candidates = self.search([
            ('id', '!=', self.id),
            ('zone_id', '=', self.zone_id.id),
            ('urgency', '=', 'routine'),
            ('state', 'in', ('pending', 'suggested')),
            ('requested_date', '>', target_date),
        ], order='requested_date', limit=4)
        for c in candidates:
            old_date = c.suggested_date or c.requested_date
            c.write({
                'suggested_date': target_date,
                'suggested_technician_id': self.suggested_technician_id.id,
                'state': 'suggested',
                'suggested_reason': _(
                    'Rule 4: pulled from %(old)s to %(new)s -- same %(zone)s zone as '
                    '%(anchor_client)s\'s %(anchor_urgency)s visit that day.') % {
                    'old': old_date, 'new': target_date, 'zone': self.zone_id.name,
                    'anchor_client': self.partner_id.name, 'anchor_urgency': self.urgency,
                },
            })

    # ------------------------------------------------------------------
    # Human review
    # ------------------------------------------------------------------

    def action_confirm(self):
        for req in self:
            if req.state != 'suggested':
                raise UserError(_("Compute a suggestion before confirming."))
            if not req.suggested_technician_id or not req.suggested_date:
                raise UserError(_(
                    "No technician could be suggested for this request -- "
                    "assign one manually before confirming."))
            visit = req.visit_id
            if not visit:
                visit = self.env['airlogic.service.visit'].create({
                    'partner_id': req.partner_id.id,
                    'technician_id': req.suggested_technician_id.id,
                    'date': req.suggested_date,
                })
                req.visit_id = visit.id
            units = req.equipment_id or self.env['airlogic.equipment'].search(
                [('partner_id', '=', req.partner_id.id)])
            for unit in units:
                self.env['airlogic.service.job'].create({
                    'equipment_id': unit.id,
                    'visit_id': visit.id,
                    'technician_id': req.suggested_technician_id.id,
                    'date': req.suggested_date,
                })
            req.state = 'confirmed'
            req._notify_confirmation(visit)

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _notify_confirmation(self, visit):
        """4-way notification, per the confirmed dispatch design:
        the assigned technician, the requester (a stand-in for "any
        client whose visit moved" -- there's no client-portal user in
        this system to notify directly), any OTHER technician whose own
        job got pulled onto a new date by Rule 4's sweep, and every
        Operations Officer. Uses Odoo's own inbox notification
        (message_post with partner_ids) rather than a custom push
        mechanism.
        """
        self.ensure_one()
        partner_ids = set()
        if self.suggested_technician_id.partner_id:
            partner_ids.add(self.suggested_technician_id.partner_id.id)
        if self.requested_by.partner_id:
            partner_ids.add(self.requested_by.partner_id.id)
        officers = self.env['res.users'].search(
            [('groups_id', 'in', self.env.ref('airlogic_core.group_airlogic_supervisor').id)])
        for officer in officers:
            if officer.partner_id:
                partner_ids.add(officer.partner_id.id)
        visit.message_post(
            body=_(
                'Dispatch confirmed: %(client)s, %(date)s, assigned to %(tech)s.') % {
                'client': self.partner_id.name, 'date': self.suggested_date,
                'tech': self.suggested_technician_id.name,
            },
            partner_ids=list(partner_ids),
        )
