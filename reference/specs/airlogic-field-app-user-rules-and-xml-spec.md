---
title: Field Entry App & Odoo.sh Inventory — User Levels, DO/DON'T Rules, Semi-Code XML Spec
context: Standard Airlogic — Odoo.sh customization (field app + inventory)
status: Design spec only. Nothing scaffolded yet. Written for Claude Code to build from.
builds_on: hvac-unit-data-model-brief.md (4-phase walk, 3-tier data model: hvac.unit / hvac.visit / hvac.reading.line)
---

# Goal

Lock down who can do what in the field entry app and in Odoo.sh Inventory, so diagnostic
data stays trustworthy (no silent edits, no skipped phases, no unauthorized stock pulls),
while keeping the technician's screen a fast, linear walkthrough — not a form to fight with.

**Assumed roles** (from the four-person office structure — confirm before scaffolding):
Service Technician (field), Operations Officer (dispatch/supervisor), Owner/Admin,
Accounting Support (billing view-only). Adjust group names if actual titles differ.

---

# 1. User Levels — Reference Table

| Role | Odoo Group | Field App Scope | Inventory Scope |
|---|---|---|---|
| Service Technician | `group_airlogic_technician` | Own dispatched visits only; full 4-phase entry while visit is open | View stock on hand; consume/request parts tied to their own visit |
| Operations Officer (Supervisor) | `group_airlogic_supervisor` | All visits (dispatch-wide); review, flag, approve revisions | Approve part requests above a peso threshold; view all consumption |
| Owner / Admin | `group_airlogic_admin` | Full CRUD; manages thresholds, users, groups | Full CRUD; manages product catalog, vendor pricing, stock adjustments |
| Accounting Support | `group_airlogic_accounting` | Read-only, Completed/Closed visits only (for billing/sign-off) | Read-only cost data tied to closed visits (for invoicing) |

Each group implies the one below it (`admin ⊃ supervisor ⊃ technician`) except Accounting,
which is a separate side-branch with no field-app write access at all.

---

# 2. DO / DON'T — Account & Access

| DO | DON'T |
|---|---|
| Log in with individually assigned technician accounts | Share one login across multiple technicians |
| Restrict the technician's dispatch list to jobs assigned to them, today | Show the full company-wide job list to a technician |
| Require Supervisor+ to reassign a visit to a different technician | Let a technician self-reassign or "steal" another tech's job |
| Log every login/logout with timestamp + device | Allow silent/anonymous app access |

---

# 3. DO / DON'T — 4-Phase Walkthrough Entry

| DO | DON'T |
|---|---|
| Lock Phase 2 (Outdoor–ON) until Phase 1 (Outdoor–OFF) required fields are complete | Let a technician jump straight to Line Set and back-fill earlier phases |
| Default visual/smell/touch items to "Normal"; tap only to flag an exception | Force the technician to tap-confirm every item as fine |
| Auto-flag numeric readings red when outside the pre-loaded pass/fail threshold | Let a technician manually override a flagged reading without a note |
| Pre-fill thresholds from the manufacturer reference table (Bluon / Daikin BTSC / Mitsubishi MN-1) | Hard-code thresholds inside the app where only Admin can't adjust them |
| Require a one-line reason when a technician overrides a flag as "acceptable" | Allow flag overrides with no explanation logged |

---

# 4. DO / DON'T — Photos & Attachments

| DO | DON'T |
|---|---|
| Auto-tag smart-glasses photos with phase + timestamp + geo at capture | Require the technician to manually name/file photos afterward |
| Attach the MeasureQuick report as a single PDF to the Visit | Re-type MeasureQuick's pressure/temp/superheat/subcool values into separate fields |
| Allow technicians to add photos while a visit is open | Allow technicians to delete a photo once attached — only Supervisor+ can remove, with a logged reason |

---

# 5. DO / DON'T — Submission, Locking & Back-Revisions

| DO | DON'T |
|---|---|
| Lock all Reading Lines the moment a Visit status becomes **Completed** | Allow a technician to edit values on a Completed visit directly |
| Route any post-submission correction through a **Revision Request** (old value, new value, reason — mandatory) | Let anyone silently overwrite a submitted reading, even to "fix a typo" |
| Require Supervisor+ approval before a revision applies | Let a technician self-approve their own revision request |
| Preserve the original value permanently once a revision is approved (old + new both visible in history) | Delete or hide the original value after a correction |
| Let Admin only see aggregate revision-rate per technician (feeds documentation-completeness incentive metric) | Let revision rate be invisible to the incentive system — it's a proxy for documentation integrity, don't let it go untracked |

**Why this matters here specifically:** subcooling/superheat and the manual readings are the
whole diagnostic-integrity pitch. A field app that lets values get quietly edited after the
fact undermines the exact thing that differentiates Standard Airlogic from feel-based
competitors like Randy's model — the audit trail has to be real, not decorative.

---

# 6. DO / DON'T — Parts & Inventory Consumption

| DO | DON'T |
|---|---|
| Let a technician view current stock on hand for the parts relevant to their job | Let a technician view wholesale cost/vendor pricing — that's Admin-only |
| Let a technician log parts consumed against their own open Visit | Let a technician adjust on-hand inventory counts directly |
| Route any part request above a set peso threshold (TBD — see open items) to Supervisor approval | Auto-approve high-value part requests with no second check |
| Let Admin manage the product catalog, reorder points, and vendor pricing | Let Supervisor or Technician create new products/SKUs |
| Tie every stock deduction to a Visit ID for costing (feeds Hoshi cost-per-unit tracking) | Allow "loose" stock deductions with no job reference |

---

# 7. DO / DON'T — Offline & Sync (field connectivity)

| DO | DON'T |
|---|---|
| Allow a technician to complete all 4 phases offline and queue the submission | Block data entry entirely when signal drops mid-job |
| Sync automatically the moment connectivity returns, in the background | Require the technician to manually re-enter data after reconnecting |
| Timestamp readings at the moment of capture, not at sync time | Let sync time overwrite the actual capture time — this breaks the audit trail |
| Warn (not block) if a visit has been open >X hours without syncing | Silently lose unsynced data with no local queue |

---

# 8. App Walkthrough — Technician Flow

This is the simple, linear flow the technician sees. Each step only unlocks the next.

1. **Log in** → today's dispatch list (own jobs only, sorted by SLA window).
2. **Tap a job** → Unit summary loads (read-only asset info + last visit's health status).
3. **Tap "Start Visit"** → status flips `Scheduled → In Progress`, timestamp starts.
4. **Phase 1 — Outdoor, Power OFF**: tap-only checklist + number-pad readings.
5. **Phase 2 — Outdoor, Power ON** *(unlocks only after Phase 1 required fields are filled)*.
6. **Phase 3 — Indoor Unit**.
7. **Phase 4 — Line Set**.
8. **Attach MeasureQuick PDF** — one tap, no manual re-entry of its readings.
9. **Review screen** — flagged items highlighted; submission is blocked if a required field is blank.
10. **Submit** → status flips to `Completed`, all Reading Lines lock, technician now sees read-only.
11. **Supervisor review** *(off the technician's device)* → `Closed`, or sends back as `Flagged` with a Revision Request if something needs correction.

---

# 9. Back-Revision Workflow (state view)

```
Scheduled → In Progress → Completed (locked)
                              │
                              ├─ Supervisor reviews within SLA → Closed
                              │
                              └─ Correction needed → Revision Requested
                                      │
                                      ├─ Supervisor approves → value updated,
                                      │     original preserved in revision history → Closed
                                      │
                                      └─ Supervisor rejects → stays Completed/Flagged,
                                            reason logged, no value change
```

---

# 10. Semi-Code — Security Groups (XML)

```xml
<record id="group_airlogic_technician" model="res.groups">
    <field name="name">Field Technician</field>
</record>

<record id="group_airlogic_supervisor" model="res.groups">
    <field name="name">Operations Supervisor</field>
    <field name="implied_ids" eval="[(4, ref('group_airlogic_technician'))]"/>
</record>

<record id="group_airlogic_admin" model="res.groups">
    <field name="name">Airlogic Admin</field>
    <field name="implied_ids" eval="[(4, ref('group_airlogic_supervisor'))]"/>
</record>

<record id="group_airlogic_accounting" model="res.groups">
    <field name="name">Accounting (View Only)</field>
</record>
```

---

# 11. Semi-Code — Access Rights (`ir.model.access.csv`)

```csv
id,name,model_id,group_id,perm_read,perm_write,perm_create,perm_unlink
access_hvac_unit_technician,hvac.unit technician,model_hvac_unit,group_airlogic_technician,1,0,0,0
access_hvac_visit_technician,hvac.visit technician,model_hvac_visit,group_airlogic_technician,1,1,1,0
access_hvac_reading_line_technician,reading line technician,model_hvac_reading_line,group_airlogic_technician,1,1,1,0
access_hvac_revision_technician,revision technician,model_hvac_reading_line_revision,group_airlogic_technician,1,1,1,0
access_hvac_unit_supervisor,hvac.unit supervisor,model_hvac_unit,group_airlogic_supervisor,1,1,1,0
access_hvac_visit_supervisor,hvac.visit supervisor,model_hvac_visit,group_airlogic_supervisor,1,1,1,0
access_hvac_revision_supervisor,revision supervisor,model_hvac_reading_line_revision,group_airlogic_supervisor,1,1,0,0
access_hvac_all_admin,all models admin,model_hvac_unit,group_airlogic_admin,1,1,1,1
access_hvac_visit_accounting,hvac.visit accounting,model_hvac_visit,group_airlogic_accounting,1,0,0,0
```

*(Split into one row per model in the real file — combined here for readability.)*

---

# 12. Semi-Code — Record Rules (`ir.rule`)

```xml
<!-- Technician sees only their own assigned visits -->
<record id="rule_visit_technician_own" model="ir.rule">
    <field name="name">Technician: own visits only</field>
    <field name="model_id" ref="model_hvac_visit"/>
    <field name="domain_force">[('technician_id','=',user.id)]</field>
    <field name="groups" eval="[(4, ref('group_airlogic_technician'))]"/>
</record>

<!-- Lock: technician can't write to a Reading Line once its Visit is Completed,
     unless an approved revision has explicitly reopened it -->
<record id="rule_reading_line_lock" model="ir.rule">
    <field name="name">Lock reading lines after Completed except open revision</field>
    <field name="model_id" ref="model_hvac_reading_line"/>
    <field name="domain_force">
        ['|', ('visit_id.state','not in',['completed','flagged','closed']),
              ('revision_open','=',True)]
    </field>
    <field name="groups" eval="[(4, ref('group_airlogic_technician'))]"/>
    <field name="perm_write">1</field>
    <field name="perm_create">0</field>
    <field name="perm_unlink">0</field>
</record>

<!-- Accounting: only Completed/Flagged/Closed visits, read-only -->
<record id="rule_visit_accounting_closed_only" model="ir.rule">
    <field name="name">Accounting: closed-stage visits only</field>
    <field name="model_id" ref="model_hvac_visit"/>
    <field name="domain_force">[('state','in',['completed','flagged','closed'])]</field>
    <field name="groups" eval="[(4, ref('group_airlogic_accounting'))]"/>
</record>
```

---

# 13. Semi-Code — State Field & Workflow Buttons

```python
state = fields.Selection([
    ('draft', 'Scheduled'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('flagged', 'Flagged'),
    ('closed', 'Closed'),
], default='draft', tracking=True)

revision_open = fields.Boolean(default=False, tracking=True)
```

```xml
<button name="action_start_visit" string="Start Visit" type="object"
        states="draft" groups="airlogic.group_airlogic_technician"/>

<button name="action_submit_visit" string="Submit" type="object"
        states="in_progress" groups="airlogic.group_airlogic_technician"/>

<button name="action_request_revision" string="Request Correction" type="object"
        states="completed,flagged" groups="airlogic.group_airlogic_technician"/>

<button name="action_approve_revision" string="Approve Correction" type="object"
        attrs="{'invisible': [('revision_open','=',False)]}"
        groups="airlogic.group_airlogic_supervisor"/>

<button name="action_close_visit" string="Close" type="object"
        states="completed,flagged" groups="airlogic.group_airlogic_supervisor"/>
```

---

# 14. Semi-Code — Revision (Back-Revision) Model

```python
class HvacReadingLineRevision(models.Model):
    _name = 'hvac.reading.line.revision'
    _inherit = ['mail.thread']

    reading_line_id = fields.Many2one('hvac.reading.line', required=True)
    old_value = fields.Char(required=True)
    new_value = fields.Char(required=True)
    reason = fields.Text(required=True)
    requested_by = fields.Many2one('res.users', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users')
    state = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='requested', tracking=True)
```

Add `_inherit = ['mail.thread']` and `tracking=True` on the key fields of `hvac.visit`
and `hvac.reading.line` too — this gives a free chatter-based audit log as a second layer
on top of the explicit revision model, in case a value change happens through a path the
revision workflow didn't anticipate.

---

# 15. Open Items to Confirm Before Scaffolding

- Odoo.sh version/hosting — still unconfirmed from the earlier data-model brief.
- Peso threshold that triggers Supervisor approval on a part request.
- Whether "Flagged" visits auto-notify the Supervisor, or require a manual daily scan.
- Offline sync behavior on the actual Odoo mobile app version in use — offline support
  varies by release; verify before assuming full offline capture works out of the box.
- Exact list of fields that require a mandatory reason on revision (all, or only numeric
  readings vs. visual-item flags).
