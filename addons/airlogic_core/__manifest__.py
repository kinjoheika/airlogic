# -*- coding: utf-8 -*-
{
    'name': 'Standard Airlogic',
    'version': '19.0.1.0.0',
    'category': 'Services/Field Service',
    'summary': 'Aircon service field entry: equipment, service jobs, configurable measurement fields',
    'description': """
Standard Airlogic — Phase 0-2
==============================

First vertical slices of the Standard Airlogic aircon-service app, ported
from the aircon-service-ui HTML mockup onto real Odoo 19 models:

- airlogic.equipment: one row per aircon unit (client, sublocation, model,
  serial number, type)
- airlogic.service.job: one row per technician visit to a unit
- airlogic.measurement.field: the Fieldpiece JobLink 30-field measurement
  list as *data*, not code — editable under Configuration so field labels,
  units, sections, and manufacturer standards can be changed without a
  deploy
- airlogic.reading.line: one value per (job, measurement field); a job's
  lines auto-populate from the active measurement fields on creation

Deliberately plain Odoo backend views (list/form, no OWL) for this first
pass, per AIR-P2 scope decision — priority is correct data model and
working create/read/write, not visual parity with the mockup yet.
""",
    'author': 'Standard Airlogic',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'mail', 'account'],
    'data': [
        'security/airlogic_security.xml',
        'security/ir.model.access.csv',
        'data/airlogic_sequence_data.xml',
        'data/airlogic_measurement_field_data.xml',
        'data/airlogic_equipment_category_data.xml',
        'views/airlogic_measurement_field_views.xml',
        'views/airlogic_equipment_category_views.xml',
        'views/airlogic_service_visit_views.xml',
        # service_job must load before equipment: the equipment form's
        # smart button references action_airlogic_service_job via
        # %(...)d, which is resolved at XML-load time, not at runtime.
        'views/airlogic_service_job_views.xml',
        'views/airlogic_equipment_views.xml',
        'views/airlogic_menus.xml',
        'reports/airlogic_parts_reference_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'airlogic_core/static/src/scss/airlogic.scss',
            'airlogic_core/static/src/field_entry/field_entry.js',
            'airlogic_core/static/src/field_entry/field_entry.xml',
            'airlogic_core/static/src/field_entry/field_entry.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
