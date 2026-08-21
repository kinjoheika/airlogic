# -*- coding: utf-8 -*-
from odoo import models


class AirlogicOwnerReport(models.AbstractModel):
    """Data provider for the Owner Full Report -- Option A PDF (the
    mockup's chosen/finalized owner report template). Per visit: header
    facts, per-status counts, and a unit-by-unit breakdown with real
    photos and real flagged-checklist issues -- no fabricated
    cost-estimate or system-diagram content that isn't backed by data
    this addon actually tracks (see AIR-T19 commit message for the
    deliberate omissions vs. the mockup).
    """
    _name = 'report.airlogic_core.report_airlogic_owner_report'
    _description = 'Airlogic Owner Service Report'

    def _get_report_values(self, docids, data=None):
        visits = self.env['airlogic.service.visit'].browse(docids)
        visit_data = {}
        for visit in visits:
            jobs_info = []
            counts = {'good': 0, 'watch': 0, 'urgent': 0}
            for job in visit.job_ids:
                status = visit._job_status(job)
                counts[status] += 1
                jobs_info.append({
                    'job': job,
                    'status': status,
                    'issues': visit._job_issues(job),
                    'photos': job.media_ids.filtered(
                        lambda a: a.mimetype and a.mimetype.startswith('image/'))[:3],
                })
            visit_data[visit.id] = {
                'jobs_info': jobs_info,
                'counts': counts,
                'total': len(visit.job_ids),
            }
        return {
            'doc_ids': docids,
            'doc_model': 'airlogic.service.visit',
            'docs': visits,
            'visit_data': visit_data,
        }
