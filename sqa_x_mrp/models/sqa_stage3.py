from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class SqaStage3(models.Model):
    _name = 'sqa.stage3'
    _description = 'SQA Stage 3 - Final Costing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    pre_order_ref = fields.Char(string='Pre-Order Reference', readonly=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    stage1_id = fields.Many2one('sqa.stage1', string='Stage 1', readonly=True)
    stage2_id = fields.Many2one('sqa.stage2', string='Stage 2', readonly=True)
    sqa_stage3_line_ids = fields.One2many('sqa.stage3.line', 'stage3_id', string='BOM Lines')
    grand_total_cost = fields.Float(compute='_compute_grand_totals', store=True, string='Grand Total Cost')
    grand_total_sales = fields.Float(compute='_compute_grand_totals', store=True, string='Grand Total Sales Price')
    state = fields.Selection([('draft', 'Draft'), ('checked', 'Checked')], default='draft', tracking=True)

    @api.depends('sqa_stage3_line_ids.total_cost', 'sqa_stage3_line_ids.total_sales')
    def _compute_grand_totals(self):
        for rec in self:
            rec.grand_total_cost = sum(rec.sqa_stage3_line_ids.mapped('total_cost'))
            rec.grand_total_sales = sum(rec.sqa_stage3_line_ids.mapped('total_sales'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sqa.stage3') or _('New')
        return super().create(vals_list)

    def action_check(self):
        employee = self.env.user.employee_id
        if not employee or employee.sqa_role != 's3':
            raise UserError(_('Only SQA Role S3 (Final Costing) can check Stage 3.'))
        if not self.sqa_stage3_line_ids:
            raise ValidationError(_('No BOM lines found.'))
        self.state = 'checked'
        self.message_post(body=_('Stage 3 checked. Ready for Final Stage.'))
        return True


class SqaStage3Line(models.Model):
    _name = 'sqa.stage3.line'
    _description = 'SQA Stage 3 BOM Line'

    stage3_id = fields.Many2one('sqa.stage3', ondelete='cascade', required=True)
    bom_id = fields.Many2one('mrp.bom', string='BOM / Product', required=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    total_cost = fields.Float(compute='_compute_totals', store=True, string='Total Cost Price')
    total_sales = fields.Float(compute='_compute_totals', store=True, string='Total Sales Price')
    sqa_stage3_bom_id = fields.Many2one('sqa.stage3.bom', ondelete='cascade')

    @api.depends(
        'sqa_stage3_bom_id.bom_line_ids.product_qty',
        'sqa_stage3_bom_id.bom_line_ids.cost_price',
        'sqa_stage3_bom_id.bom_line_ids.sales_price',
    )
    def _compute_totals(self):
        for rec in self:
            lines = rec.sqa_stage3_bom_id.bom_line_ids if rec.sqa_stage3_bom_id else []
            rec.total_cost = sum(l.product_qty * l.cost_price for l in lines)
            rec.total_sales = sum(l.product_qty * l.sales_price for l in lines)

    def action_open_bom_wizard(self):
        self.ensure_one()
        if not self.sqa_stage3_bom_id or not self.sqa_stage3_bom_id.id:
            bom_rec = self.env['sqa.stage3.bom'].create({
                'bom_id': self.bom_id.id,
                'product_qty': self.product_qty,
                'stage3_line_id': self.id,
                'bom_line_ids': [(0, 0, {
                    'product_id': bl.product_id.id,
                    'product_qty': bl.product_qty,
                    'cost_price': bl.product_id.standard_price,
                    'sales_price': bl.product_id.list_price,
                }) for bl in self.bom_id.bom_line_ids],
            })
            self.sqa_stage3_bom_id = bom_rec.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOM Detail — %s') % self.bom_id.display_name,
            'res_model': 'sqa.stage3.bom',
            'res_id': self.sqa_stage3_bom_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class SqaStage3Bom(models.Model):
    _name = 'sqa.stage3.bom'
    _description = 'SQA Stage 3 BOM Wizard'

    stage3_line_id = fields.Many2one('sqa.stage3.line', ondelete='cascade')
    bom_id = fields.Many2one('mrp.bom', string='BOM / Product', required=True, readonly=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    bom_line_ids = fields.One2many('sqa.stage3.bom.line', 'stage3_bom_id', string='Component Lines')
    total_cost = fields.Float(compute='_compute_totals', store=True, string='Total Cost Price')
    total_sales = fields.Float(compute='_compute_totals', store=True, string='Total Sales Price')

    @api.depends('bom_line_ids.product_qty', 'bom_line_ids.cost_price', 'bom_line_ids.sales_price')
    def _compute_totals(self):
        for rec in self:
            rec.total_cost = sum(l.product_qty * l.cost_price for l in rec.bom_line_ids)
            rec.total_sales = sum(l.product_qty * l.sales_price for l in rec.bom_line_ids)

    def action_save_and_close(self):
        return {'type': 'ir.actions.act_window_close'}


class SqaStage3BomLine(models.Model):
    _name = 'sqa.stage3.bom.line'
    _description = 'SQA Stage 3 BOM Component Line'

    stage3_bom_id = fields.Many2one('sqa.stage3.bom', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Component', required=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    cost_price = fields.Float(string='Cost Price')
    sales_price = fields.Float(string='Sales Price')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.cost_price = self.product_id.standard_price
            self.sales_price = self.product_id.list_price
