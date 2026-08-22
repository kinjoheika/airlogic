# -*- coding: utf-8 -*-
{
    'name': 'Inventory',
    'version': '19.0.1.0.0',
    'category': 'Services/Field Service',
    'summary': 'Aircon equipment, parts reference, client visits and invoicing',
    'description': """
Inventory (formerly Standard Airlogic)
=======================================

Client-site equipment/device inventory, configurable Categories/Brands/
HP/Sublocations, the Parts Reference PDF, and Service Visits with
per-category invoicing. The technician field-entry workflow (mobile
app, measurements, visual checklist, PDF import, photos) lives in the
separate Field Service module, which depends on this one and extends
Equipment/Visit via inheritance to add job-aware features -- this
module itself has no knowledge of airlogic.service.job.
""",
    'author': 'Standard Airlogic',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'mail', 'account'],
    'data': [
        'security/airlogic_security.xml',
        'security/ir.model.access.csv',
        'data/airlogic_sequence_data.xml',
        'data/airlogic_equipment_category_data.xml',
        'data/airlogic_equipment_lookup_data.xml',
        'views/airlogic_equipment_category_views.xml',
        'views/airlogic_equipment_lookup_views.xml',
        'views/airlogic_service_visit_views.xml',
        'views/airlogic_equipment_views.xml',
        'views/airlogic_menus.xml',
        'reports/airlogic_parts_reference_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'airlogic_core/static/src/scss/airlogic.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
