# -*- coding: utf-8 -*-
from openerp import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    ts_line_ids = fields.One2many('hr.analytic.timesheet', 'task_id')

    failing_field = fields.Float(compute='_get_invoiced_hours', store=True)

    @api.one
    # This would pervent creation of timesheet lines
    # as task_id (counter part of ts_line_ids) is defined on the analytic line
    # whereas the ts_line_ids is defined on hr.analytic.timesheet
    @api.depends('ts_line_ids')
    def _get_invoiced_hours(self):
        """ Sum timesheet line invoiced hours """
        self.failing_field = len(self.work_ids)


class AnalyticAccountLine(models.Model):
    _inherit = 'account.analytic.line'

    task_id = fields.Many2one('project.task')
