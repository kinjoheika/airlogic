# -*- coding: utf-8 -*-
from itertools import groupby
from operator import attrgetter

from odoo import models


class AirlogicPartsReferenceReport(models.AbstractModel):
    """Data provider for the Parts Reference QWeb PDF. Groups whatever
    airlogic.equipment records were selected/printed by client, then by
    sublocation within each client -- printing per client per sublocation
    is a matter of which equipment the user selects before printing, not
    a separate wizard.
    """
    _name = 'report.airlogic_core.report_airlogic_parts_reference'
    _description = 'Airlogic Parts Reference Report'

    def _get_report_values(self, docids, data=None):
        equipment = self.env['airlogic.equipment'].browse(docids)
        equipment = equipment.sorted(
            key=lambda e: (e.partner_id.name or '', e.sublocation_id.name or '', e.name or ''))

        groups = []
        for partner, by_partner in groupby(equipment, key=attrgetter('partner_id')):
            sublocations = []
            for subloc, by_sub in groupby(by_partner, key=attrgetter('sublocation_id')):
                sublocations.append({
                    'sublocation': subloc.name if subloc else '—',
                    'equipment': list(by_sub),
                })
            groups.append({'partner': partner, 'sublocations': sublocations})

        return {
            'doc_ids': docids,
            'doc_model': 'airlogic.equipment',
            'docs': equipment,
            'groups': groups,
        }
