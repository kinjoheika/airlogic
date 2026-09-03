# -*- coding: utf-8 -*-
"""post_init_hook, not static XML: backfilling 4 fully-completed past
visits (readings + checklist) for every demo unit is ~10 units x 4
visits x ~55 fields -- impractical to hand-author, and it needs
airlogic.service.job/reading.line/checklist.line, which don't exist
yet when airlogic_core's own demo data (airlogic_demo_seed_data.xml)
loads. This has to run in Field Service's own post_init_hook, once
both modules (and their data) are guaranteed installed.

Purpose: give the mobile app's Units > Readings/Checklist comparison
tables (which show up to 3 past visits per unit) real historical data
to display instead of "No readings yet for this unit."
"""
import base64
import random
from datetime import timedelta

from odoo import fields

from .models.airlogic_checklist_line import CHECKLIST_ITEMS

DEMO_CLIENT_NAMES = ['Meridian Business Park', 'Cornerstone Residences', 'Bayview Grand Hotel']
VISITS_PER_UNIT = 4
DAYS_BETWEEN_VISITS = 100
FLAG_CHANCE = 0.12

# 1x1 transparent PNG -- smallest possible valid image, used only to
# give a job SOME real ir.attachment to test photo-heavy rendering
# against (AIR-T64's stress-test seed), not to look like anything.
TINY_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB'
    'AScY42YAAAAASUVORK5CYII=')

STRESS_TAG = '[STRESS TEST]'

WEIRD_NOTE_SAMPLES = [
    'Emoji: unit smoking, evacuated the room immediately. Fire risk flagged.',
    '特殊字符测试: client-facing text field holding non-Latin characters.',
    'Quote/apostrophe test: client said "it\'s not cooling" -- tech\'s reply: broken pipe.',
    '<script>alert(1)</script> XSS probe: this must render as literal text, never execute.',
    'Ampersand & less-than < greater-than > characters in a free-text field.',
    'Tab\tand\nnewline\ncharacters embedded in a single note field.',
]


def _random_reading_value(field, rng):
    """Plausible-looking value for one measurement field, keyed off its
    unit -- not real HVAC physics, just enough variation across the 4
    visits to make a comparison table worth looking at.
    """
    if field.code == 'ref_type':
        return rng.choice(['R-410A', 'R-32', 'R-22'])
    unit = field.unit or ''
    ranges = {
        '°C': (4, 28, 1),
        '%': (35, 65, 1),
        'psi': (60, 250, 1),
        'CFM': (700, 1600, 0),
        'BTU/h': (9000, 48000, 0),
        'Btu/lbm': (20, 40, 1),
    }
    low, high, ndigits = ranges.get(unit, (1, 100, 1))
    return str(round(rng.uniform(low, high), ndigits))


def seed_demo_service_history(env):
    equipment = env['airlogic.equipment'].search([
        ('partner_id.name', 'in', DEMO_CLIENT_NAMES),
    ])
    if not equipment:
        return
    job_model = env['airlogic.service.job']
    if job_model.search_count([('equipment_id', 'in', equipment.ids)]):
        return  # already seeded (e.g. a module upgrade re-running this hook)

    item_type_by_key = {key: item_type for _phase, key, _label, item_type, _unit in CHECKLIST_ITEMS}
    rng = random.Random(42)  # deterministic across runs, not security-sensitive
    now = fields.Datetime.now()

    for equip in equipment:
        for i in range(VISITS_PER_UNIT):
            visit_date = now - timedelta(days=DAYS_BETWEEN_VISITS * (VISITS_PER_UNIT - i))
            job = job_model.create({
                'equipment_id': equip.id,
                'date': visit_date,
            })
            for line in job.reading_line_ids:
                line.value = _random_reading_value(line.field_id, rng)
            for line in job.checklist_line_ids:
                item_type = item_type_by_key.get(line.key)
                if item_type == 'text':
                    continue
                elif item_type == 'number':
                    line.value = str(round(rng.uniform(1, 5), 1))
                elif item_type == 'leak':
                    line.value = 'pass'
                elif rng.random() < FLAG_CHANCE:
                    line.value = rng.choice(['flagged', 'alert'])
                    line.note = 'Noted during inspection -- monitor next visit.'
                else:
                    line.value = 'ok'
            job.write({'state': 'submitted', 'started_at': visit_date})


# ---------------------------------------------------------------------
# Stress-test data (AIR-T64): 30 Service Visits deliberately built to
# sit at or past the edges of what the rest of this addon assumes --
# empty visits, huge visits, blank/extreme/non-numeric readings,
# leaks, very long and Unicode/XSS-probe text, null relational fields,
# past/future/missing dates, a subscription-linked visit, an unzoned
# dispatch request, missing vendor pricing, and a few deliberately
# "boring/clean" controls to compare against. Every job's notes field
# is prefixed with "[STRESS TEST]" so the whole batch is one search
# away to review or delete later. Manually triggered (Configuration >
# Seed Stress-Test Data), not a post_init_hook: re-running it adds
# another fresh batch rather than being a one-time install step, since
# the point is to have data ready for a testing pass whenever needed.
# ---------------------------------------------------------------------

def _get_or_create_stress_client(env):
    """20-unit client, used only for the "many jobs on one visit"
    boundary cases -- none of the real demo clients have more than 4
    units, nowhere near enough to stress page-break/pagination
    behavior in the reports.
    """
    partner = env['res.partner'].search([('name', '=', 'Stress Test Client (Many Units)')], limit=1)
    if partner:
        return partner
    partner = env['res.partner'].create({
        'name': 'Stress Test Client (Many Units)',
        'is_company': True,
        'city': 'Makati City',
    })
    # category_id is required=True on airlogic.equipment -- fall back to
    # any configured category rather than the specific demo one, so
    # this doesn't break if the demo xmlid isn't there for some reason.
    category = env.ref('airlogic_core.cat_split_wall', raise_if_not_found=False) \
        or env['airlogic.equipment.category'].search([], limit=1)
    brand = env.ref('airlogic_core.brand_carrier', raise_if_not_found=False)
    hp = env.ref('airlogic_core.hp_1', raise_if_not_found=False)
    for i in range(1, 21):
        sub = env['airlogic.sublocation'].create({'name': 'Stress Test Zone %d' % i})
        env['airlogic.equipment'].create({
            'name': 'AC Unit %d - Stress Test' % i,
            'partner_id': partner.id,
            'sublocation_id': sub.id,
            'category_id': category.id,
            'brand_id': brand.id if brand else False,
            'hp_id': hp.id if hp else False,
            'model': 'STRESS-%03d' % i,
            'serial_number': 'STR-2026-%05d' % i,
            'install_year': 2020,
        })
    return partner


def _attach_photos(env, job, count):
    atts = env['ir.attachment']
    for i in range(count):
        atts |= env['ir.attachment'].create({
            'name': 'stress_%s_%d.png' % (job.id, i),
            'type': 'binary',
            'datas': base64.b64encode(TINY_PNG),
            'mimetype': 'image/png',
        })
    job.media_ids = [(4, a.id) for a in atts]


def seed_stress_test_visits(env):
    rng = random.Random(20260903)
    now = fields.Datetime.now()

    partners = {p.name: p for p in env['res.partner'].search(
        [('name', 'in', DEMO_CLIENT_NAMES + ['Rizal Tower Offices', 'Manila Grand Suites'])])}
    meridian = partners.get('Meridian Business Park')
    cornerstone = partners.get('Cornerstone Residences')  # deliberately unzoned
    bayview = partners.get('Bayview Grand Hotel')
    rizal = partners.get('Rizal Tower Offices')
    grand = partners.get('Manila Grand Suites')
    stress_client = _get_or_create_stress_client(env)

    def units_of(partner, limit=None):
        eqs = env['airlogic.equipment'].search([('partner_id', '=', partner.id)])
        return eqs[:limit] if limit else eqs

    def new_visit(partner, date=None, state=None, reviewed=False, contract=False):
        vals = {'partner_id': partner.id}
        if date is not None:
            vals['date'] = date
        visit = env['airlogic.service.visit'].create(vals)
        if reviewed:
            visit.reviewed_by_id = env.user.id
        if contract:
            visit.contract_id = contract.id
        if state:
            visit.write({'state': state})
        return visit

    def new_job(visit, equipment, note_suffix='', readings=None, checklist=None, submit=True):
        job = env['airlogic.service.job'].create({
            'equipment_id': equipment.id,
            'visit_id': visit.id,
        })
        job.notes = ('%s %s' % (STRESS_TAG, note_suffix)).strip()
        if readings:
            for line in job.reading_line_ids:
                if line.field_id.code in readings:
                    line.value = readings[line.field_id.code]
        if checklist:
            for line in job.checklist_line_ids:
                if line.key in checklist:
                    val = checklist[line.key]
                    if isinstance(val, tuple):
                        line.value, line.note = val
                    else:
                        line.value = val
        if submit:
            job.write({'state': 'submitted', 'started_at': visit.date or now})
        return job

    all_field_codes = env['airlogic.measurement.field'].search([]).mapped('code')
    extreme_readings = {code: '99999' for code in all_field_codes}  # forces out-of-range on any field with a max set
    blank_readings = {code: '' for code in all_field_codes}
    ol_readings = {code: 'OL' for code in all_field_codes}
    negative_readings = {'amp_draw': '-3', 'cfm_outdoor': '0', 'cfm_indoor': '-15'}

    v = []  # keep every created visit, purely so a caller could inspect the batch

    # 1. Empty visit: zero jobs at all.
    v.append(new_visit(meridian, state='review'))

    # 2. All-blank readings and checklist on an otherwise normal job.
    visit = new_visit(bayview)
    new_job(visit, units_of(bayview, 1)[0], 'all-blank readings/checklist', readings=blank_readings)
    v.append(visit)

    # 3. Every numeric reading forced out of range.
    visit = new_visit(meridian)
    new_job(visit, units_of(meridian, 1)[0], 'every reading forced out-of-range', readings=extreme_readings)
    v.append(visit)

    # 4. Leak detected across multiple spots, with a note.
    visit = new_visit(bayview)
    new_job(visit, units_of(bayview)[-1], 'multi-spot leak',
            checklist={'leak': ('0,2,4,6', 'Leak found at 4 separate points along the suction line.')})
    v.append(visit)

    # 5. Extremely long technician notes + a long issue note.
    visit = new_visit(cornerstone)
    long_text = 'Extended inspection notes. ' + ('Checked coil, drain, wiring, and refrigerant charge. ' * 60)
    j = new_job(visit, units_of(cornerstone, 1)[0], long_text,
                checklist={'pcb': ('flagged', 'Corrosion observed near terminal block. ' * 20)})
    v.append(visit)

    # 6-11. Unicode / XSS / quote / ampersand / whitespace probes, one per visit.
    weird_units = list(units_of(rizal)) + list(units_of(grand))
    for i, sample in enumerate(WEIRD_NOTE_SAMPLES):
        visit = new_visit(weird_units[i % len(weird_units)].partner_id)
        new_job(visit, weird_units[i % len(weird_units)], sample)
        v.append(visit)

    # 12. 20-job visit: every stress-client unit on one visit.
    visit = new_visit(stress_client)
    for eq in units_of(stress_client):
        new_job(visit, eq, '20-unit visit boundary test')
    v.append(visit)

    # 13. 12-job visit.
    visit = new_visit(stress_client)
    for eq in units_of(stress_client, 12):
        new_job(visit, eq, '12-unit visit boundary test')
    v.append(visit)

    # 14. 6-job visit (a more realistic "large but plausible" visit).
    visit = new_visit(stress_client)
    for eq in units_of(stress_client, 6):
        new_job(visit, eq, '6-unit visit')
    v.append(visit)

    # 15. Negative/zero numeric values.
    visit = new_visit(grand)
    new_job(visit, units_of(grand, 1)[0], 'negative/zero readings', readings=negative_readings)
    v.append(visit)

    # 16. "OL" (Fieldpiece over-limit marker) in every numeric field.
    visit = new_visit(rizal)
    new_job(visit, units_of(rizal, 1)[0], 'OL in every reading', readings=ol_readings)
    v.append(visit)

    # 17. Visit dated far in the past.
    v.append(new_visit(meridian, date=fields.Datetime.to_string(now - timedelta(days=365 * 11)), state='approved', reviewed=True))
    new_job(v[-1], units_of(meridian, 1)[0], 'dated 11 years in the past')

    # 18. Visit dated far in the future.
    v.append(new_visit(bayview, date=fields.Datetime.to_string(now + timedelta(days=365 * 5))))
    new_job(v[-1], units_of(bayview, 1)[0], 'dated 5 years in the future')

    # 19. Visit with no date at all.
    visit = env['airlogic.service.visit'].create({'partner_id': cornerstone.id, 'date': False})
    new_job(visit, units_of(cornerstone, 1)[0], 'no date set on the visit')
    v.append(visit)

    # 20. Subscription-linked visit (tests the double-invoice guard).
    contract = env['airlogic.service.contract'].create({
        'partner_id': meridian.id, 'billing_period': 'quarterly', 'price': 5000.0,
    })
    visit = new_visit(meridian, state='approved', reviewed=True, contract=contract)
    new_job(visit, units_of(meridian, 1)[0], 'subscription-linked visit')
    v.append(visit)

    # 21. Approved visit whose only job is still Draft (inconsistent state combo).
    visit = new_visit(bayview, state='approved', reviewed=True)
    new_job(visit, units_of(bayview, 1)[0], 'approved visit, job left in draft', submit=False)
    v.append(visit)

    # 22. Equipment with every OPTIONAL relational field left blank
    # (category_id is required=True on the model, so that one stays
    # set -- brand_id/hp_id/sublocation_id are the genuinely nullable
    # ones this tests, e.g. "No sublocation"/"No brand" fallback text
    # throughout the mobile app, reports, and Compatible Parts).
    bare_partner = meridian
    any_category = env['airlogic.equipment.category'].search([], limit=1)
    bare_equip = env['airlogic.equipment'].create({
        'name': 'AC Unit - No Sublocation/Brand/HP',
        'partner_id': bare_partner.id,
        'category_id': any_category.id,
    })
    visit = new_visit(bare_partner)
    new_job(visit, bare_equip, 'equipment with every optional field left blank')
    v.append(visit)

    # 23. Extremely long client/equipment/model names.
    long_name = 'Extremely Long Client Name For Layout Stress Testing ' * 4
    long_partner = env['res.partner'].create({'name': long_name[:250], 'is_company': True})
    long_sub = env['airlogic.sublocation'].create({'name': 'Sublocation ' + ('X' * 100)})
    long_equip = env['airlogic.equipment'].create({
        'name': 'AC Unit - ' + ('Very Long Equipment Name ' * 6),
        'partner_id': long_partner.id,
        'sublocation_id': long_sub.id,
        'category_id': any_category.id,
        'model': 'MODEL-' + ('9' * 80),
    })
    visit = new_visit(long_partner)
    new_job(visit, long_equip, 'long client/equipment/model name stress test')
    v.append(visit)

    # 24. 14 photos on one job (dense photo-grid stress).
    visit = new_visit(meridian)
    j = new_job(visit, units_of(meridian, 1)[0], '14 photos on one job')
    _attach_photos(env, j, 14)
    v.append(visit)

    # 25. Multiple simultaneous flagged/alert checklist issues on one job.
    visit = new_visit(cornerstone)
    new_job(visit, units_of(cornerstone)[-1], 'many simultaneous issues', checklist={
        'brk': ('flagged', 'Breaker terminal loose.'),
        'comp': ('alert', 'Compressor housing warmer than expected.'),
        'coils': ('flagged', 'Coil fins bent in several spots.'),
        'pcb': ('alert', 'PCB has minor discoloration.'),
        'wires': ('flagged', 'Exposed wire near junction box.'),
    })
    v.append(visit)

    # 26. Part Request + Consumable Request against parts with no vendor
    # configured (none of the demo parts have product.supplierinfo set
    # up) -- exercises the "no vendor configured yet" fallback path.
    visit = new_visit(stress_client)
    j = new_job(visit, units_of(stress_client, 1)[0], 'part/consumable request with no vendor configured')
    part = env['product.product'].search([('airlogic_requestable', '=', True)], limit=1)
    if part:
        req = env['airlogic.part.request'].create({'job_id': j.id, 'part_id': part.id})
        req.action_approve()
    consumable = env['product.product'].search([('airlogic_is_consumable', '=', True)], limit=1)
    if consumable:
        creq = env['airlogic.consumable.request'].create({'product_id': consumable.id, 'quantity': 3})
        creq.action_approve()
    v.append(visit)

    # 27. A Revision Request left pending against a submitted job.
    visit = new_visit(bayview, state='approved', reviewed=True)
    j = new_job(visit, units_of(bayview, 1)[0], 'job with a pending revision request')
    line = j.reading_line_ids[:1]
    if line:
        env['airlogic.job.revision'].create({
            'job_id': j.id,
            'line_model': 'reading',
            'field_label': line.field_id.name,
            'line_key': line.field_id.code,
            'old_value': line.value or '',
            'new_value': '42',
            'reason': STRESS_TAG + ' testing a pending revision request display',
        })
    v.append(visit)

    # 28. Unzoned client (Cornerstone) with a Dispatch Request left
    # Pending -- exercises the "no zone match" fallback in Rule 3.
    env['airlogic.dispatch.request'].create({
        'partner_id': cornerstone.id,
        'equipment_id': units_of(cornerstone, 1)[0].id,
        'urgency': 'rush',
        'source': 'call_in',
        'notes': STRESS_TAG + ' unzoned client, tests the no-zone-match fallback',
    })

    # 29. "Everything at once" torture job: long/weird text, out-of-
    # range readings, a leak, several issues, negative values, and a
    # stack of photos, all on one job.
    visit = new_visit(meridian, state='approved', reviewed=True)
    torture_readings = dict(extreme_readings)
    torture_readings.update(negative_readings)
    j = new_job(visit, units_of(meridian)[-1],
                WEIRD_NOTE_SAMPLES[0] + ' ' + long_text[:300],
                readings=torture_readings,
                checklist={
                    'leak': ('0,1,2,3,4,5,6,7', 'Leak everywhere -- worst-case scenario.'),
                    'brk': ('flagged', 'Everything wrong at once.'),
                    'comp': ('alert', 'See above.'),
                })
    _attach_photos(env, j, 6)
    v.append(visit)

    # 30. Two visits for the same client on the same day (same-day
    # multiple-visit boundary case).
    same_day = fields.Datetime.to_string(now)
    visit_a = new_visit(bayview, date=same_day)
    new_job(visit_a, units_of(bayview, 1)[0], 'first of two same-day visits')
    visit_b = new_visit(bayview, date=same_day)
    new_job(visit_b, units_of(bayview)[-1], 'second of two same-day visits')
    v.extend([visit_a, visit_b])

    return v
