# -*- coding: utf-8 -*-
{
    'name': 'Field Service',
    'version': '19.0.1.0.0',
    'category': 'Services/Field Service',
    'summary': 'Technician field entry: mobile app, measurements, visual checklist, PDF import, photos',
    'description': """
Field Service
=============

Split out of the Inventory (formerly Standard Airlogic) module so the
technician-facing field-work app has its own home in Odoo's Apps grid,
separate from equipment/parts/client management. Depends on Inventory
for Equipment and Service Visit, and extends both via inheritance to
add the job-aware bits (stat button, Reading/Visual Comparison tabs,
invoicing, the Owner Report) -- Inventory itself has no knowledge of
airlogic.service.job.

- Field Entry (Mobile): OWL app -- Client -> Equipment -> Job, with
  phase tabs for Measurements, Visual Checklist, PDF Import, and
  Photos. Local-first save + offline sync queue for
  readings/checklist/PDF (not photos).
- airlogic.service.job / reading.line / checklist.line: the 30-field
  Fieldpiece measurement grid and the 21-item Ph1-4 visual checklist.
- airlogic.measurement.field: the 30-field list as configurable data.
- Owner Full Report -- Option A: per-visit PDF, plus the invoicing
  (priced per unit per category) that only Field Service can compute,
  since it needs job/equipment data.
""",
    'author': 'Standard Airlogic',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'mail', 'account', 'purchase', 'airlogic_core'],
    'data': [
        'security/ir.model.access.csv',
        'security/airlogic_ir_rule.xml',
        'data/airlogic_sequence_data.xml',
        'data/airlogic_measurement_field_data.xml',
        'data/airlogic_history_tag_data.xml',
        'data/airlogic_part_data.xml',
        'data/airlogic_seed_action_data.xml',
        'data/airlogic_app_config_data.xml',
        'data/airlogic_report_paperformat_data.xml',
        'data/airlogic_service_contract_cron_data.xml',
        'views/airlogic_measurement_field_views.xml',
        'views/airlogic_history_tag_views.xml',
        'views/airlogic_part_views.xml',
        'views/airlogic_app_config_views.xml',
        'views/airlogic_job_revision_views.xml',
        'views/airlogic_equipment_ext_views.xml',
        'views/airlogic_equipment_category_ext_views.xml',
        'views/airlogic_service_job_views.xml',
        'views/airlogic_service_visit_ext_views.xml',
        'views/airlogic_service_contract_views.xml',
        'views/airlogic_mobile_app_views.xml',
        'views/airlogic_res_users_views.xml',
        'reports/airlogic_owner_report.xml',
        'reports/airlogic_site_visit_reports.xml',
        'views/airlogic_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # field_entry.js only exports PHASES/LEAK_SPOTS now (see the
            # file's own header comment) -- mobile_app.js imports them
            # via the @airlogic_field_service/field_entry/field_entry
            # module path, so this still has to stay registered even
            # though its .xml/.scss companions (the desktop checklist
            # component they belonged to) are gone.
            'airlogic_field_service/static/src/field_entry/field_entry.js',
            'airlogic_field_service/static/src/mobile_app/mobile_app.js',
            'airlogic_field_service/static/src/mobile_app/mobile_app.xml',
            'airlogic_field_service/static/src/mobile_app/mobile_app.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    # Backfills 4 past visits (readings + checklist) for the demo
    # equipment seeded in airlogic_core's airlogic_demo_seed_data.xml --
    # see hooks.py for why this runs as a hook, not static XML.
    'post_init_hook': 'seed_demo_service_history',
}
