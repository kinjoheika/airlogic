# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .airlogic_checklist_line import CHECKLIST_ITEMS


class AirlogicServiceJob(models.Model):
    _name = 'airlogic.service.job'
    _description = 'Airlogic Service Job'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', default='/', copy=False, tracking=True)
    visit_id = fields.Many2one(
        'airlogic.service.visit', string='Visit', ondelete='set null', tracking=True)
    equipment_id = fields.Many2one(
        'airlogic.equipment', string='Equipment', required=True, tracking=True)
    partner_id = fields.Many2one(
        related='equipment_id.partner_id', string='Client', store=True, readonly=True)
    technician_id = fields.Many2one(
        'res.users', string='Technician', default=lambda self: self.env.user, tracking=True)
    date = fields.Datetime(string='Visit Date', default=fields.Datetime.now, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
    ], string='Status', default='draft', tracking=True)
    visit_state = fields.Selection(
        related='visit_id.state', string='Visit Stage', store=True, readonly=True,
        help="Mirrors the parent Service Visit's own Draft/For Review/"
             "Approved progress as a badge on the job, so that stage is "
             "visible without opening the Visit. Deliberately a separate "
             "field from `state` above (the technician's own Draft/In "
             "Progress/Submitted DSR workflow): the various submission-"
             "lock checks throughout this addon compare state == "
             "'submitted', and a Visit moving on to For Review/Approved "
             "must never make that comparison go False and silently "
             "reopen editing on an already-submitted job.")
    started_at = fields.Datetime(
        string='Started At', tracking=True,
        help='Set once, the first time the technician actually opens the '
             'entry screen (action_start_visit) -- kept separate from Visit '
             'Date so this stays an honest capture-time record even if '
             'Visit Date is edited later.')
    notes = fields.Text(string='Tech Notes')
    reading_line_ids = fields.One2many(
        'airlogic.reading.line', 'job_id', string='Measurements')
    checklist_line_ids = fields.One2many(
        'airlogic.checklist.line', 'job_id', string='Visual Checklist')
    fp_pdf = fields.Binary(string='Fieldpiece PDF', attachment=True)
    fp_pdf_filename = fields.Char(string='Fieldpiece PDF Filename')
    media_ids = fields.Many2many(
        'ir.attachment', string='Photos / Videos',
        help='Job-site photos and videos. Stored as normal Odoo attachments '
             '-- if the filestore is later moved to object storage (e.g. '
             'Cloudflare R2), these move transparently with it.')
    history_tag_ids = fields.Many2many(
        'airlogic.history.tag', string='History Tags', copy=False,
        help='Set automatically on submit by keyword-matching notes/flagged '
             'checklist items against Configuration > History Tags. Drives '
             "the mobile app's Unit History feed.")
    revision_open = fields.Boolean(
        default=False, copy=False, tracking=True,
        help='Briefly True while an approved airlogic.job.revision is '
             'being applied -- the only window in which reading/checklist '
             'lines can be written once this job is Submitted (see '
             'rule_reading_line_lock_submitted / '
             'rule_checklist_line_lock_submitted in airlogic_ir_rule.xml). '
             'Not meant to be toggled by hand.')
    revision_ids = fields.One2many(
        'airlogic.job.revision', 'job_id', string='Revision Requests')
    part_request_ids = fields.One2many(
        'airlogic.part.request', 'job_id', string='Part Requests')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_technician_reassignment(vals_list)
        jobs = super().create(vals_list)
        for job in jobs:
            if job.name == '/':
                job.name = self.env['ir.sequence'].next_by_code('airlogic.service.job') or '/'
            if not job.reading_line_ids:
                job._populate_reading_lines()
            if not job.checklist_line_ids:
                job._populate_checklist_lines()
        return jobs

    def write(self, vals):
        if 'technician_id' in vals:
            self._check_technician_reassignment([vals])
        if 'media_ids' in vals and not self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            self._check_no_media_removal(vals['media_ids'])
        return super().write(vals)

    def _check_no_media_removal(self, commands):
        """Only Supervisor+ can remove an attached photo/video. (2,) and
        (3,) commands are both a removal (delete-the-record vs. just
        unlink-the-relation); a (6, 0, ids) replace-all command is a
        removal too if it drops any id the job currently has. Adding via
        (4,)/a bigger (6, 0, ids) is untouched -- technicians can still
        upload freely.
        """
        for cmd in commands:
            if cmd[0] in (2, 3):
                raise AccessError(_(
                    "Only an Operations Officer or Manager can remove a photo/video "
                    "once attached."))
            if cmd[0] == 6:
                new_ids = set(cmd[2])
                for job in self:
                    if not set(job.media_ids.ids) <= new_ids:
                        raise AccessError(_(
                            "Only an Operations Officer or Manager can remove a photo/video "
                            "once attached."))

    def action_request_revision(self):
        """Opens a blank airlogic.job.revision form pre-linked to this
        job -- the technician (or anyone) fills in which item, old/new
        value, and a reason; Supervisor+ approves or rejects it from
        there. See airlogic_job_revision.py for the actual apply/lock
        mechanics.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request Correction'),
            'res_model': 'airlogic.job.revision',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_job_id': self.id},
        }

    def _check_technician_reassignment(self, vals_list):
        """Only Supervisor+ can assign/reassign a job to a technician other
        than the acting user -- mirrors airlogic.service.visit's guard in
        airlogic_core (same rationale: technician_id defaults to
        self.env.user, so a technician claiming their own default job is
        fine, handing it to or taking it from someone else is not).
        """
        if self.env.user.has_group('airlogic_core.group_airlogic_supervisor'):
            return
        for vals in vals_list:
            tech_id = vals.get('technician_id')
            if tech_id and tech_id != self.env.user.id:
                raise AccessError(_(
                    "Only an Operations Officer or Manager can assign or reassign "
                    "the technician on a Service Job."))

    def _populate_reading_lines(self):
        self.ensure_one()
        fields_active = self.env['airlogic.measurement.field'].search([])
        self.env['airlogic.reading.line'].create([
            {'job_id': self.id, 'field_id': f.id}
            for f in fields_active
        ])

    def _populate_checklist_lines(self):
        self.ensure_one()
        self.env['airlogic.checklist.line'].create([
            {'job_id': self.id, 'phase': phase, 'key': key, 'label': label}
            for phase, key, label, item_type, unit in CHECKLIST_ITEMS
        ])

    def action_start_visit(self):
        """First real step of the 4-phase walkthrough: flips draft ->
        in_progress and stamps started_at. Idempotent -- called
        automatically the moment the mobile app opens the entry screen
        (see enterDsr() in mobile_app.js), not as a separate tap, so the
        walkthrough stays fast while still recording an honest start
        time. Safe to call again on an already-started job; only acts
        while still draft.
        """
        for job in self:
            if job.state == 'draft':
                job.write({'state': 'in_progress', 'started_at': fields.Datetime.now()})

    def action_submit(self):
        for job in self:
            if job.state != 'in_progress':
                raise UserError(_(
                    "Start the visit before submitting -- readings can't "
                    "be locked in from Draft."))
        self._match_history_tags()
        self.write({'state': 'submitted'})

    def _phase_required_keys(self, phase):
        """Only 'number' items gate phase completion -- actual measured
        readings (Amp Draw, Megger, etc.) that must be entered, not
        back-filled later. 'check' items are deliberately excluded: they
        default to Normal and are only touched to flag an exception (see
        the mobile app's Flag/Alert dialog), so most stay blank/unset for
        the whole visit by design -- requiring a value on them here would
        make a phase with any check items never register as complete.
        'leak' and 'text' are Ph4-only and never factor into unlocking
        anything (nothing comes after Ph4).
        """
        return [key for ph, key, label, item_type, unit in CHECKLIST_ITEMS
                if ph == phase and item_type == 'number']

    def get_unlocked_phase(self):
        """Highest phase number (1-4) the technician may currently enter
        data into: phase N+1 unlocks only once every required item in
        phase N has a value. Phase 4 has nothing after it to unlock, so
        the loop only walks phases 1-3.

        Deliberately `all(...)` with no `required and` guard: all([]) is
        True, so a phase with zero 'number' items (Phase 3, "Indoor OFF",
        now that Anemometer (Indoor) moved to Phase 1) is trivially
        complete rather than stuck forever. An earlier version guarded
        on `required and ...`, which made a check-only phase never
        register as complete -- the same bug AIR-T35 fixed for Phase 2
        before Anemometer (Indoor) existed here to mask it for Phase 3.
        """
        self.ensure_one()
        values_by_key = {line.key: line.value for line in self.checklist_line_ids}
        unlocked = 1
        for phase in (1, 2, 3):
            required = self._phase_required_keys(phase)
            if all(values_by_key.get(key) for key in required):
                unlocked = phase + 1
            else:
                break
        return unlocked

    def _match_history_tags(self):
        """Keyword-match this job's notes + flagged/alert checklist item
        notes against active History Tags. Run once, at submit time --
        not a recomputed field, so re-editing a submitted job's notes
        doesn't silently change its history classification.
        """
        tags = self.env['airlogic.history.tag'].search([])
        tag_keywords = [
            (tag, [k.strip().lower() for k in (tag.keywords or '').split(',') if k.strip()])
            for tag in tags
        ]
        for job in self:
            text_parts = [job.notes or '']
            for line in job.checklist_line_ids:
                if line.value in ('flagged', 'alert'):
                    text_parts.append(line.label or '')
                    text_parts.append(line.note or '')
            haystack = ' '.join(text_parts).lower()
            matched = self.env['airlogic.history.tag']
            for tag, keywords in tag_keywords:
                if any(kw in haystack for kw in keywords):
                    matched |= tag
            job.history_tag_ids = [(6, 0, matched.ids)]

    def action_save_visual_checklist(self, values, notes=None):
        """Called by the OWL client actions' Done/flag-dialog Save via the
        ORM service. values: dict of item key -> entered value. notes:
        dict of item key -> note text (mainly for alert/flagged items).

        Two integrity checks live here (not just in the mobile UI) so
        they hold regardless of which client calls this -- mobile app or
        the desktop Visual Checklist action:
        - Phase lock: can't write into a phase beyond get_unlocked_phase().
        - Override reason: clearing a flagged/alert item back to 'ok'
          needs a non-blank note, either passed in this same call or
          already on the line.
        """
        self.ensure_one()
        lines_by_key = {line.key: line for line in self.checklist_line_ids}
        unlocked = self.get_unlocked_phase()
        notes = notes or {}
        for key, val in (values or {}).items():
            line = lines_by_key.get(key)
            if line is None:
                continue
            if line.phase > unlocked:
                raise UserError(_(
                    "Phase %(phase)d is locked until Phase %(prev)d's "
                    "required items are complete.") % {
                        'phase': line.phase, 'prev': line.phase - 1})
            if line.value in ('flagged', 'alert') and val == 'ok':
                reason = (notes.get(key) or line.note or '').strip()
                if not reason:
                    raise UserError(_(
                        "A reason is required when clearing a flagged/alert "
                        "item back to Normal."))
            line.value = val
        for key, note in notes.items():
            line = lines_by_key.get(key)
            if line is not None:
                line.note = note
        return True

    def action_save_reading_lines(self, values):
        """Called from the mobile field-entry app. values: dict of
        measurement field code -> entered value.
        """
        self.ensure_one()
        lines_by_code = {line.field_id.code: line for line in self.reading_line_ids}
        for code, val in (values or {}).items():
            line = lines_by_code.get(code)
            if line is not None:
                line.value = val
        return True

    def get_field_entry_data(self):
        """Single-call data fetch for the mobile field-entry app, so it
        doesn't need several separate search_read round-trips per job.
        """
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'started_at': self.started_at and fields.Datetime.to_string(self.started_at),
            'unlocked_phase': self.get_unlocked_phase(),
            'equipment_name': self.equipment_id.display_name,
            'has_pdf': bool(self.fp_pdf),
            'media_count': len(self.media_ids),
            'reading_lines': [{
                'code': line.field_id.code,
                'label': line.field_id.name,
                'section': line.section,
                'unit': line.unit,
                'standard': line.standard,
                'sequence': line.sequence,
                'value': line.value,
                'is_out_of_range': line.is_out_of_range,
                'min_value': line.field_id.min_value,
                'max_value': line.field_id.max_value,
            } for line in self.reading_line_ids],
            'checklist_lines': [{
                'key': line.key,
                'label': line.label,
                'phase': line.phase,
                'value': line.value,
                'note': line.note,
            } for line in self.checklist_line_ids],
        }

    @api.model
    def _extract_pdf_lines(self, pdf_bytes):
        """Return the PDF's text as a list of stripped, non-empty lines.
        Imported lazily (not at module load) so a missing pypdf on this
        Odoo instance can't crash the whole registry -- only this button.
        """
        try:
            import pypdf
        except ImportError:
            try:
                import PyPDF2 as pypdf
            except ImportError:
                raise UserError(_(
                    "No PDF library is available on this Odoo instance "
                    "(tried pypdf and PyPDF2). Ask your odoo.sh admin to "
                    "add 'pypdf' to the Python requirements."))
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() or '' for page in reader.pages)
        return [line.strip() for line in text.splitlines() if line.strip()]

    def action_import_fieldpiece_pdf(self):
        self.ensure_one()
        if not self.fp_pdf:
            raise UserError(_("Attach a Fieldpiece PDF report first."))
        lines = self._extract_pdf_lines(base64.b64decode(self.fp_pdf))
        filled = 0
        for line_rec in self.reading_line_ids:
            label = line_rec.field_id.pdf_label or line_rec.field_id.name
            for line in lines:
                if not line.startswith(label):
                    continue
                raw = line[len(label):].strip()
                if not raw or raw == '-':
                    break
                unit = line_rec.field_id.unit
                if unit and raw.endswith(unit):
                    raw = raw[:-len(unit)].strip()
                line_rec.value = raw
                filled += 1
                break
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fieldpiece PDF imported'),
                'message': _('%(filled)d of %(total)d fields filled from the PDF.') % {
                    'filled': filled, 'total': len(self.reading_line_ids)},
                'type': 'success' if filled else 'warning',
            },
        }

    @api.model
    def action_seed_demo_service_history(self):
        """Thin wrapper so the "Re-seed Demo Service History" server
        action (data/airlogic_seed_action_data.xml) doesn't need an
        `import` statement in its own code -- ir.actions.server's
        state='code' runs in a safe_eval sandbox that forbids
        IMPORT_NAME/IMPORT_FROM outright (a bad import there doesn't
        just fail the action, it fails to even PARSE and takes the whole
        registry down). A plain import inside a regular model method
        like this one is unrestricted, same as the lazy `import pypdf`
        above -- the server action just calls this method instead.
        """
        from ..hooks import seed_demo_service_history
        seed_demo_service_history(self.env)

    @api.model
    def action_seed_stress_test_data(self):
        """Same reasoning as action_seed_demo_service_history above: the
        import has to live in a plain model method, not directly in the
        server action's own sandboxed code (AIR-T64).
        """
        from ..hooks import seed_stress_test_visits
        seed_stress_test_visits(self.env)
