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
from openerp import models, fields, api, _, exceptions, SUPERUSER_ID

STATES = [
    ('draft', "Draft"),
    ('confirm', "Confirmed"),
]


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.multi
    def _get_default_invoiced_hours(self):
        return self.unit_amount

    @api.multi
    def _get_default_invoiced_product(self):
        return self.product_id

    state = fields.Selection(
        STATES,
        required=True,
        default='draft',
    )

    invoiced_hours = fields.Float(
        default=_get_default_invoiced_hours,
        help="Amount of hours that you want to charge your customer for (e.g. "
             "hours spent 2:12, invoiced 2:15). You can use the 'Create "
             "invoice' wizard from timesheet line for that purpose",
    )
    invoiced_product = fields.Many2one(
        'product.product',
        default=_get_default_invoiced_product,
        help="Product used to generate the invoice in case it differs from the"
             " product used to compute the costs.",
    )

    @api.multi
    def _check(self):
        """ OVERWRITE _check to check state of the line instead of the sheet
        """
        for line in self:
            if line.state == 'confirmed':
                if (self.env.user != line.account_id.user_id and
                        self.env.uid != SUPERUSER_ID):
                    raise exceptions.Warning(
                        _("Only the project manager can modify an entry in a "
                          "confirmed timesheet line. Please contact him to set"
                          " this entry to draft in order to edit it."))
        return True

    @api.multi
    def write(self, vals):
        """ Only project manager can change states """
        if 'state' in vals:
            if (self.env.user != self.account_id.user_id and
                    self.env.uid != SUPERUSER_ID):
                raise exceptions.Warning(
                    _("Only the project manager can modify state of an entry.")
                )
        return super(AccountAnalyticLine, self).write(vals)

    @api.multi
    def _get_invoice_grouping_key(self):
        """ Get key for grouping in invoicing """
        product = (self.invoiced_product or
                   self.product_id)
        return (product.id,
                self.product_uom_id.id,
                self.user_id.id,
                self.to_invoice.id,
                self.account_id,
                self.journal_id.type)

    @api.multi
    def action_confirm(self):
        self.env.user.has_group('project.group_project_manager')
        self.write({'state': 'confirm'})

    @api.multi
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    @api.one
    @api.onchange('to_invoice')
    def onchange_to_invoice_set_invoiced_hours(self):
        """ Change invoiced_hours according to invoicing rate factor """
        if self.to_invoice:
            discount = self.unit_amount * (self.to_invoice.factor / 100.0)
            self.invoiced_hours = self.unit_amount - discount

    @api.multi
    def invoice_cost_create(self, data=None):
        """ OVERWRITE invoice_cost_create to redefine grouping of analytic
        lines for invoicing
        """
        invoice_obj = self.env['account.invoice']
        invoice_line_obj = self.env['account.invoice.line']
        invoices = []
        if data is None:
            data = {}

        # use key (partner/account, company, currency)
        # creates one invoice per key
        invoice_grouping = {}

        currency_id = False
        # prepare for iteration on journal and accounts
        for line in self:

            key = (line.account_id.id,
                   line.account_id.company_id.id,
                   line.account_id.pricelist_id.currency_id.id)
            invoice_grouping.setdefault(key, []).append(line)

        for keys, analytic_lines in invoice_grouping.items():
            (key_id, company_id, currency_id) = keys
            # key_id is an account.analytic.account
            account = analytic_lines[0].account_id
            partner = account.partner_id  # will be the same for every line
            if (not partner) or not (currency_id):
                raise exceptions.Warning(
                    _('Contract incomplete. Please fill in the Customer and '
                      'Pricelist fields for %s.') % (account.name))

            curr_invoice = self._prepare_cost_invoice(
                partner, company_id, currency_id, analytic_lines)
            invoice_context = self.env.context.copy()
            invoice_context.update(
                lang=partner.lang,
                # set force_company in context so the correct product
                # properties are selected
                # (eg. income account) lang=partner.lang,
                force_company=company_id,
                # set company_id in context, so the correct default journal
                # will be selected
                company_id=company_id
            )
            last_invoice = invoice_obj.with_context(
                invoice_context
            ).create(curr_invoice)
            invoices.append(last_invoice)

            # use key (product, uom, user, invoiceable, analytic account,
            # journal type)
            # creates one invoice line per key
            invoice_lines_grouping = {}
            for analytic_line in analytic_lines:
                account = analytic_line.account_id

                if not analytic_line.to_invoice:
                    raise exceptions.Warning(
                        _('Error!'),
                        _('Trying to invoice non invoiceable line for %s.'
                          ) % (analytic_line.product_id.name))

                #################
                # CHANGE IS HERE
                key = analytic_line._get_invoice_grouping_key()
                # CHANGE END
                #################

                # We want to retrieve the data in the partner language for the
                # invoice creation
                analytic_line = analytic_line.with_context(invoice_context)
                invoice_lines_grouping.setdefault(key, []).append(
                    analytic_line)

            self_inv_cxt = self.with_context(invoice_context)

            # finally creates the invoice line
            for keys, lines_to_invoice in invoice_lines_grouping.items():
                (product_id, uom, uid, factor_id, account, journal_type) = keys
                curr_invoice_line = self_inv_cxt._prepare_cost_invoice_line(
                    last_invoice, product_id, uom, uid, factor_id,
                    account, lines_to_invoice, journal_type, data)

                invoice_line_obj.create(curr_invoice_line)
            analytic_lines.write({'invoice_id': last_invoice})
            invoice_obj.button_reset_taxes([last_invoice])
        return invoices

    @api.model
    def _prepare_cost_invoice_line(self, invoice_id, product_id, uom, user_id,
                                   factor_id, account, analytic_lines,
                                   journal_type, data):
        """
        Override to add unit_price computation and quantity based on
        invoiced_hours
        """
        _super = super(AccountAnalyticLine, self)
        curr_invoice_line = _super._prepare_cost_invoice_line(
            invoice_id, product_id, uom, user_id, factor_id, account,
            analytic_lines, journal_type, data)

        total_qty = sum(l.invoiced_hours or l.unit_amount
                        for l in analytic_lines)
        total_price = sum(l.amount for l in analytic_lines)

        if data.get('product'):
            # force product, use its public price
            if isinstance(data['product'], (tuple, list)):
                product_id = data['product'][0]
            else:
                product_id = data['product']
            unit_price = self.with_context(uom=uom)._get_invoice_price(
                account, product_id, user_id, total_qty)
        elif journal_type == 'general' and product_id:
            # timesheets, use sale price
            unit_price = self.with_context(uom=uom)._get_invoice_price(
                account, product_id, user_id, total_qty)
        else:
            # expenses, using price from amount field
            unit_price = total_price * -1.0 / total_qty

        curr_invoice_line.update({
            'price_unit': unit_price,
            'quantity': total_qty,
        })
        return curr_invoice_line
