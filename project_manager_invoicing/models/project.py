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
from openerp import models, fields, api, osv


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Due to https://github.com/odoo/odoo/issues/8461
    # we cannot use api 8.0 field
    @api.multi
    def _get_invoiced_hours(self, names, args):
        """ Sum timesheet line invoiced hours """
        res = {}
        for task in self:
            res[task.id] = sum(l.invoiced_hours for l in self.work_ids)
        return res

    @api.multi
    def _get_analytic_line(self):
        result = []
        for aal in self:
            if aal.task_id:
                result.append(aal.task_id.id)
        return result

    _columns = {
        'invoiced_hours': osv.fields.function(
            _get_invoiced_hours,
            type='float',
            store={'project.task': (lambda self, cr, uid, ids, c=None: ids,
                                    ['work_ids'], 20),
                   'account.analytic.line': (_get_analytic_line,
                                             ['task_id', 'invoiced_hours'], 20)
                   }
        ),
    }

    remaining_hours = fields.Float(
        compute='_get_remaining_hours', store=True,
        help="Total remaining time based on invoiced hours"
    )

    @api.one
    @api.depends('planned_hours', 'invoiced_hours')
    def _get_remaining_hours(self):
        self.remaining_hours = self.planned_hours - self.invoiced_hours
