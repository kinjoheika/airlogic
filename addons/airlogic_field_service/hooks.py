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
import random
from datetime import timedelta

from odoo import fields

from .models.airlogic_checklist_line import CHECKLIST_ITEMS

DEMO_CLIENT_NAMES = ['Meridian Business Park', 'Cornerstone Residences', 'Bayview Grand Hotel']
VISITS_PER_UNIT = 4
DAYS_BETWEEN_VISITS = 100
FLAG_CHANCE = 0.12


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
