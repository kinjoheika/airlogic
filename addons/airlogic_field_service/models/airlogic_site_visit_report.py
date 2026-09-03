# -*- coding: utf-8 -*-
from odoo import models

# Phase 1's readings run on every unit regardless of type/brand (unlike
# Phase 2/3's more component-specific electrical tests), so they're the
# closest thing to a universal "vitals" set -- what the Readings report
# (Report B) calls out as a unit's "main numbers", alongside anything
# flagged out-of-range regardless of which phase it's from.
VITAL_CODES = {'amp_draw', 'cfm_outdoor', 'cfm_indoor'}


def _build_visit_data(env, visit, include_readings):
    """Shared by both Site Visit report data providers below -- same
    per-unit status/issues/photos airlogic.service.visit._job_status /
    _job_issues already compute for the Owner Report, so all 3 reports
    agree on what "urgent" or "an issue" means. include_readings=False
    is Report A (status only); True is Report B (adds each unit's main
    numbers).
    """
    jobs_info = []
    for job in visit.job_ids:
        status = visit._job_status(job)
        photos = job.media_ids.filtered(lambda a: a.mimetype and a.mimetype.startswith('image/'))
        readings = []
        if include_readings:
            for line in job.reading_line_ids:
                if not line.value:
                    continue
                if line.field_id.code in VITAL_CODES or line.is_out_of_range:
                    readings.append({
                        'label': line.field_id.name,
                        'value': line.value,
                        'unit': line.unit,
                        'out_of_range': line.is_out_of_range,
                    })
        jobs_info.append({
            'job': job,
            'status': status,
            'issues': visit._job_issues(job),
            'readings': readings,
            'photos': photos,
        })
    return {
        'jobs_info': jobs_info,
        'has_photos': any(ji['photos'] for ji in jobs_info),
        'total': len(visit.job_ids),
    }


def _get_standards(env):
    """Configuration > Measurement Fields' own standard/min/max, reused
    as-is for the last page's reference table -- see the report
    template's own comment for why this lives in Configuration, not a
    new per-client model.
    """
    return env['airlogic.measurement.field'].search(
        [('standard', '!=', False)], order='sequence')


class AirlogicSiteVisitSimpleReport(models.AbstractModel):
    """Report A: status only, no reading numbers -- the compact
    reference version.
    """
    _name = 'report.airlogic_field_service.report_airlogic_site_visit_simple'
    _description = 'Airlogic Site Visit Report — Simple'

    def _get_report_values(self, docids, data=None):
        visits = self.env['airlogic.service.visit'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'airlogic.service.visit',
            'docs': visits,
            'visit_data': {v.id: _build_visit_data(self.env, v, False) for v in visits},
            'standards': _get_standards(self.env),
        }


class AirlogicSiteVisitReadingsReport(models.AbstractModel):
    """Report B: same compact status summary, plus each unit's main
    numbers (Phase 1 vitals + anything out of range).
    """
    _name = 'report.airlogic_field_service.report_airlogic_site_visit_readings'
    _description = 'Airlogic Site Visit Report — With Readings'

    def _get_report_values(self, docids, data=None):
        visits = self.env['airlogic.service.visit'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'airlogic.service.visit',
            'docs': visits,
            'visit_data': {v.id: _build_visit_data(self.env, v, True) for v in visits},
            'standards': _get_standards(self.env),
        }
