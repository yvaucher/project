# -*- coding: utf-8 -*-
# © 2015 Yannick Vaucher (Camptocamp SA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

""" Populate invoiced_hours fields of module project_manager_invoicing

"""


def migrate(cr, version):
    import pdb; pdb.set_trace()
    if not version:
        return

    query = ("SELECT id, invoice_id, account_analytic_id, close_date, type"
             "  FROM account_hours_block"
             "  ORDER BY account_analytic_id, create_date")
    cr.execute(query)
    invoice_ids = cr.fetchall()

    current_aa_id = None
    hour_block_num = 0
    for hb_id, inv_id, aa_id, close_date, hb_type in invoice_ids:
        if aa_id != current_aa_id:
            hour_block_num = 1
            current_aa_id = aa_id
            query = ("SELECT name FROM account_analytic_account "
                     "WHERE id = %s")
            cr.execute(query, (aa_id, ))
            account_name = cr.fetchone()[0]
        # Create a new analytic account to replace the hours block
        state = 'close' if close_date else 'open'
        query = (
            "INSERT INTO account_analytic_account"
            " ('name', 'state', 'type', 'parent_id')"
            " VALUES  (%s, %s, 'contract', %s)"
            " RETURNING id"
        )
        cr.execute(
            query,
            ("%s - Hours Block %s"
             % (account_name, hour_block_num),
                state,
                aa_id))
        new_aa_id = cr.fetchone()[0]

        query = ("UPDATE account_analytic_line SET account_id = %s"
                 "  WHERE invoice_id = %s")
        cr.execute(query, (new_aa_id, inv_id))

        query = ("SELECT id, account_id FROM account_analytic_line"
                 "  WHERE invoice_id = %s")
        cr.execute(query, (inv_id, ))
        hour_block_num += 1

        # Fill invoiced_hours on analytic lines
        # get the sum

        query = ("SELECT SUM(unit_amount * (1 - ts_f.factor / 100.0))"
                 "  FROM account_analytic_line AS aal"
                 "  INNER JOIN hr_timesheet_invoice_factor AS ts_f"
                 "    ON to_invoice = ts_f.id"
                 "  WHERE invoice_id = %s"
                 "    AND account_analytic_id = %s"
                 "  GROUP BY invoice_id")
        cr.execute(query, (inv_id, aa_id))
        hour_sum = cr.fetchone()[0]

        if hb_type == 'hours':
            query = ("SELECT line.price_subtotal"
                     "  FROM account_invoice_line AS line"
                     "  INNER JOIN product_product AS prod"
                     "    ON product_id = prod.id"
                     "  WHERE line.invoice_id = %s"
                     "    AND prod.is_in_hours_block"
                     )
            cr.execute(query, (inv_id, aa_id))
            invoiced = cr.fetchone()[0]
        # XXX type amount ?

        query = ("UPDATE account_analytic_line"
                 "  SET invoiced_hours = "
                 "  (unit_amount * {0} * (1 - ts_f.factor / 100.0)) / {1}"
                 "  FROM account_analytic_line AS aal"
                 "  INNER JOIN hr_timesheet_invoice_factor AS ts_f"
                 "    ON to_invoice = ts_f.id"
                 "  WHERE invoice_id = %s"
                 "    AND aal.account_analytic_id = %s"
                 "    AND account_analytic_line.id = aal.id"
                 "  GROUP BY invoice_id").format(invoiced, hour_sum)
        cr.execute(query, (inv_id, aa_id))

        # assign attachment and mail messages to account_analytic_account
        # instead of account_hours_block
        query = ("UPDATE ir_attachement"
                 "  SET res_model = 'account.analytic.account', res_id = %s"
                 "  WHERE res_model = 'account.hours.block'"
                 "    AND res_id = %s")
        cr.execute(query, (new_aa_id, hb_id))

        query = ("UPDATE mail_message"
                 "  SET model = 'account.analytic.account', res_id = %s"
                 "  WHERE model = 'account.hours.block'"
                 "    AND res_id = %s")
        cr.execute(query, (new_aa_id, hb_id))
