from odoo import api, fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    sqa_total_cost = fields.Float(
        string='Total Cost Price',
        compute='_compute_sqa_totals',
        store=True,
        help='Sum of (product_qty × standard_price) for all BOM lines'
    )
    sqa_total_sales = fields.Float(
        string='Total Sales Price',
        compute='_compute_sqa_totals',
        store=True,
        help='Sum of (product_qty × list_price) for all BOM lines'
    )

    @api.depends('bom_line_ids.product_qty', 'bom_line_ids.product_id.standard_price',
                 'bom_line_ids.product_id.list_price')
    def _compute_sqa_totals(self):
        for bom in self:
            total_cost = 0.0
            total_sales = 0.0
            for line in bom.bom_line_ids:
                total_cost += line.product_qty * line.product_id.standard_price
                total_sales += line.product_qty * line.product_id.list_price
            bom.sqa_total_cost = total_cost
            bom.sqa_total_sales = total_sales


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    sqa_cost_price = fields.Float(
        string='Cost Price',
        related='product_id.standard_price',
        readonly=True
    )
    sqa_sales_price = fields.Float(
        string='Sales Price',
        related='product_id.list_price',
        readonly=True
    )