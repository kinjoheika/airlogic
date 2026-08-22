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
    'depends': ['base', 'web', 'mail', 'account', 'airlogic_core'],
    'data': [
        'security/ir.model.access.csv',
        'data/airlogic_sequence_data.xml',
        'data/airlogic_measurement_field_data.xml',
        'data/airlogic_history_tag_data.xml',
        'views/airlogic_measurement_field_views.xml',
        'views/airlogic_history_tag_views.xml',
        'views/airlogic_equipment_ext_views.xml',
        'views/airlogic_service_job_views.xml',
        'views/airlogic_service_visit_ext_views.xml',
        'views/airlogic_mobile_app_views.xml',
        'views/airlogic_res_users_views.xml',
        'reports/airlogic_owner_report.xml',
        'views/airlogic_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'airlogic_field_service/static/src/field_entry/field_entry.js',
            'airlogic_field_service/static/src/field_entry/field_entry.xml',
            'airlogic_field_service/static/src/field_entry/field_entry.scss',
            'airlogic_field_service/static/src/mobile_app/mobile_app.js',
            'airlogic_field_service/static/src/mobile_app/mobile_app.xml',
            'airlogic_field_service/static/src/mobile_app/mobile_app.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
