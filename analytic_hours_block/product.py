# -*- coding: utf-8 -*-

from openerp import models, fields


class Product(models.Model):
    _name = "product.product"
    _inherit = 'product.product'

    is_in_hours_block = fields.Boolean(string='Accounted for hours block?',
                                       default=False,
                                       help="Specify if you want to have "
                                            "invoice lines containing this "
                                            "product to be considered for "
                                            "hours blocks.")
