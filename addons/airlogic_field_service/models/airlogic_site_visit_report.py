# -*- coding: utf-8 -*-
from odoo import models


def _build_visit_data(env, visit, include_readings, standards):
    """Shared by both Site Visit report data providers below -- same
    per-unit status/issues/photos airlogic.service.visit._job_status /
    _job_issues already compute for the Owner Report, so all 3 reports
    agree on what "urgent" or "an issue" means. include_readings=False
    is Report A (status only); True is Report B (adds a reading_matrix).

    reading_matrix is keyed (field_id, job_id) rather than one list per
    job: Report B's first page and its last (Standard Reference) page
    both iterate the exact same `standards` field list as their row
    set (AIR-T58), so the two pages line up row-for-row when flipping
    between "what we measured" and "what's normal" -- a per-job list of
    only-the-flagged-fields would give each unit a different, unaligned
    row count instead.
    """
    jobs_info = []
    for job in visit.job_ids:
        status = visit._job_status(job)
        photos = job.media_ids.filtered(lambda a: a.mimetype and a.mimetype.startswith('image/'))
        jobs_info.append({
            'job': job,
            'status': status,
            'issues': visit._job_issues(job),
            'photos': photos,
        })

    reading_matrix = {}
    if include_readings:
        standard_field_ids = set(standards.ids)
        for job_info in jobs_info:
            for line in job_info['job'].reading_line_ids:
                if line.value and line.field_id.id in standard_field_ids:
                    reading_matrix[(line.field_id.id, job_info['job'].id)] = {
                        'value': line.value,
                        'out_of_range': line.is_out_of_range,
                    }

    return {
        'jobs_info': jobs_info,
        'reading_matrix': reading_matrix,
        'has_photos': any(ji['photos'] for ji in jobs_info),
        'total': len(visit.job_ids),
    }


def _get_standards(env):
    """Configuration > Measurement Fields' own standard/min/max, reused
    as-is for both the readings table's row set and the last page's
    reference table -- see the report template's own comment for why
    this lives in Configuration, not a new per-client model.
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
        standards = _get_standards(self.env)
        return {
            'doc_ids': docids,
            'doc_model': 'airlogic.service.visit',
            'docs': visits,
            'visit_data': {v.id: _build_visit_data(self.env, v, False, standards) for v in visits},
            'standards': standards,
        }


class AirlogicSiteVisitReadingsReport(models.AbstractModel):
    """Report B: same compact status summary, plus a Field x Unit
    readings matrix that mirrors the last page's own layout exactly.
    """
    _name = 'report.airlogic_field_service.report_airlogic_site_visit_readings'
    _description = 'Airlogic Site Visit Report — With Readings'

    def _get_report_values(self, docids, data=None):
        visits = self.env['airlogic.service.visit'].browse(docids)
        standards = _get_standards(self.env)
        return {
            'doc_ids': docids,
            'doc_model': 'airlogic.service.visit',
            'docs': visits,
            'visit_data': {v.id: _build_visit_data(self.env, v, True, standards) for v in visits},
            'standards': standards,
        }
