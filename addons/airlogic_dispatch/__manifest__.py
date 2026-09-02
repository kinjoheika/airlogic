# -*- coding: utf-8 -*-
{
    'name': 'Dispatch',
    'version': '19.0.1.0.0',
    'category': 'Services/Field Service',
    'summary': 'Rules-based dispatch queue: zones, the 6-rule suggestion engine, and technician schedules',
    'description': """
Dispatch
========

Third module alongside Inventory (airlogic_core) and Field Service
(airlogic_field_service): reads Equipment/Sublocation data from
Inventory and Service Job/technician assignment from Field Service, so
it depends on both rather than being bolted onto either.

- airlogic.dispatch.zone: named zones (5 Makati, 3 Pasay, 3 Ermita to
  start) a client is tagged with, used as the proximity signal for
  dispatch since there is no real geolocation/routing data.
- airlogic.dispatch.request: one call-in/staff/technician ask (or one
  unit of a subscription contract's period) waiting for a technician +
  date. action_compute_suggestion runs the 6-rule cascade (backlog
  first, urgency tier, nearest available crew, zone sweep, client
  time-window, normal-schedule fill) and produces ONE suggestion with
  its reasoning attached -- never a silent auto-booking. A person
  always taps Confirm.
- The mobile app's new Schedule tab (a technician's own upcoming/past
  Service Jobs) and the Operations Officer's desktop calendar of every
  technician's jobs both just read airlogic.service.job, already
  native to Field Service -- built directly there (see
  airlogic_field_service's own commit for that tab), not here, so this
  module stays scoped to zones and the suggestion engine itself.
""",
    'author': 'Standard Airlogic',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'mail', 'airlogic_core', 'airlogic_field_service'],
    'data': [
        'security/ir.model.access.csv',
        'security/airlogic_ir_rule.xml',
        'data/airlogic_dispatch_sequence_data.xml',
        'data/airlogic_dispatch_zone_data.xml',
        'data/airlogic_dispatch_cron_data.xml',
        'views/airlogic_dispatch_zone_views.xml',
        'views/airlogic_dispatch_request_views.xml',
        'views/airlogic_res_partner_views.xml',
        'views/airlogic_dispatch_menus.xml',
        'data/airlogic_dispatch_demo_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
