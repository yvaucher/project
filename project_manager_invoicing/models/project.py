# -*- coding: utf-8 -*-
#
#    Author: Yannick Vaucher
#    Copyright 2015 Camptocamp SA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from openerp import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    invoiced_hours = fields.Float(compute='_get_invoiced_hours', store=True)
    remaining_hours = fields.Float(
        compute='_get_remaining_hours', store=True,
        help="Total remaining time based on invoiced hours"
    )

    @api.one
    # This would pervent creation of timesheet lines
    # as task_id (counter part of work_ids) is defined on the analytic line
    # where as the work_ids is defined on hr.analytic.timesheet
    @api.depends('work_ids')
    def _get_invoiced_hours(self):
        """ Sum timesheet line invoiced hours """
        self.invoiced_hours = sum(l.invoiced_hours for l in self.work_ids)

    @api.one
    @api.depends('planned_hours', 'invoiced_hours')
    def _get_remaining_hours(self):
        self.remaining_hours = self.planned_hours - self.invoiced_hours
