from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class SqaStage1(models.Model):
    _name = 'sqa.stage1'
    _description = 'SQA Stage 1 - Initial Costing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New')
    )
    pre_order_ref = fields.Char(
        string='Pre-Order Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New')
    )
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    sqa_stage1_line_ids = fields.One2many('sqa.stage1.line', 'stage1_id', string='BOM Lines')
    grand_total_cost = fields.Float(
        string='Grand Total Cost', compute='_compute_grand_totals', store=True
    )
    grand_total_sales = fields.Float(
        string='Grand Total Sales Price', compute='_compute_grand_totals', store=True
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('checked', 'Checked')],
        string='State', default='draft', tracking=True
    )
    stage2_id = fields.Many2one('sqa.stage2', string='Stage 2 Reference', readonly=True)

    @api.depends('sqa_stage1_line_ids.total_cost', 'sqa_stage1_line_ids.total_sales')
    def _compute_grand_totals(self):
        for rec in self:
            rec.grand_total_cost = sum(rec.sqa_stage1_line_ids.mapped('total_cost'))
            rec.grand_total_sales = sum(rec.sqa_stage1_line_ids.mapped('total_sales'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sqa.stage1') or _('New')
            if vals.get('pre_order_ref', _('New')) == _('New'):
                vals['pre_order_ref'] = self.env['ir.sequence'].next_by_code('sqa.pre.order') or _('New')
        return super().create(vals_list)

    def action_check(self):
        employee = self.env.user.employee_id
        if not employee or employee.sqa_role != 's1':
            raise UserError(_('Only SQA Role S1 (Initial Costing) can check Stage 1.'))
        if not self.sqa_stage1_line_ids:
            raise ValidationError(_('Add at least one BOM line before checking.'))
        stage2 = self.env['sqa.stage2'].create(self._prepare_stage2_vals())
        self.stage2_id = stage2.id
        self.state = 'checked'
        self.message_post(body=_('Stage 1 checked. Stage 2 created: %s') % stage2.name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sqa.stage2',
            'res_id': stage2.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _prepare_stage2_vals(self):
        line_vals = []
        for line in self.sqa_stage1_line_ids:
            # Create sqa.stage2.bom with its lines first, then link via sqa_stage2_bom_id
            bom_line_vals = []
            if line.sqa_stage1_bom_id:
                for bl in line.sqa_stage1_bom_id.bom_line_ids:
                    bom_line_vals.append((0, 0, {
                        'product_id': bl.product_id.id,
                        'product_qty': bl.product_qty,
                        'cost_price': bl.cost_price,
                        'sales_price': bl.sales_price,
                    }))
            stage2_bom = self.env['sqa.stage2.bom'].create({
                'bom_id': line.bom_id.id,
                'product_qty': line.product_qty,
                'bom_line_ids': bom_line_vals,
            })
            line_vals.append((0, 0, {
                'bom_id': line.bom_id.id,
                'product_qty': line.product_qty,
                'sqa_stage2_bom_id': stage2_bom.id,
            }))
        return {
            'pre_order_ref': self.pre_order_ref,
            'partner_id': self.partner_id.id,
            'stage1_id': self.id,
            'sqa_stage2_line_ids': line_vals,
        }

    def action_view_stage2(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sqa.stage2',
            'res_id': self.stage2_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


# ── sqa.stage1.line ──────────────────────────────────────────────────────────
class SqaStage1Line(models.Model):
    _name = 'sqa.stage1.line'
    _description = 'SQA Stage 1 BOM Line'

    stage1_id = fields.Many2one('sqa.stage1', ondelete='cascade', required=True)
    bom_id = fields.Many2one('mrp.bom', string='BOM / Product', required=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    total_cost = fields.Float(compute='_compute_totals', store=True, string='Total Cost Price')
    total_sales = fields.Float(compute='_compute_totals', store=True, string='Total Sales Price')

    # One sqa.stage1.bom per line — the wizard
    sqa_stage1_bom_id = fields.Many2one('sqa.stage1.bom', ondelete='cascade')

    @api.depends(
        'sqa_stage1_bom_id.bom_line_ids.product_qty',
        'sqa_stage1_bom_id.bom_line_ids.cost_price',
        'sqa_stage1_bom_id.bom_line_ids.sales_price',
    )
    def _compute_totals(self):
        for rec in self:
            lines = rec.sqa_stage1_bom_id.bom_line_ids if rec.sqa_stage1_bom_id else []
            rec.total_cost = sum(l.product_qty * l.cost_price for l in lines)
            rec.total_sales = sum(l.product_qty * l.sales_price for l in lines)

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        """Load BOM components once when bom_id is first selected."""
        if not self.bom_id or self.sqa_stage1_bom_id:
            return
        self.product_qty = self.bom_id.product_qty
        bom_line_vals = [(0, 0, {
            'product_id': bl.product_id.id,
            'product_qty': bl.product_qty,
            'cost_price': bl.product_id.standard_price,
            'sales_price': bl.product_id.list_price,
        }) for bl in self.bom_id.bom_line_ids]
        self.sqa_stage1_bom_id = self.env['sqa.stage1.bom'].new({
            'bom_id': self.bom_id.id,
            'product_qty': self.product_qty,
            'bom_line_ids': bom_line_vals,
        })

    def action_open_bom_wizard(self):
        """
        Called when user clicks a row in the BOM Lines list.
        Opens sqa.stage1.bom form directly as a dialog — no intermediate form.
        Creates the bom record first if not yet persisted.
        """
        self.ensure_one()
        if not self.sqa_stage1_bom_id or not self.sqa_stage1_bom_id.id:
            bom_line_vals = [(0, 0, {
                'product_id': bl.product_id.id,
                'product_qty': bl.product_qty,
                'cost_price': bl.product_id.standard_price,
                'sales_price': bl.product_id.list_price,
            }) for bl in self.bom_id.bom_line_ids]
            bom_rec = self.env['sqa.stage1.bom'].create({
                'bom_id': self.bom_id.id,
                'product_qty': self.product_qty,
                'stage1_line_id': self.id,
                'bom_line_ids': bom_line_vals,
            })
            self.sqa_stage1_bom_id = bom_rec.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOM Detail — %s') % self.bom_id.display_name,
            'res_model': 'sqa.stage1.bom',
            'res_id': self.sqa_stage1_bom_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


# ── sqa.stage1.bom ───────────────────────────────────────────────────────────
class SqaStage1Bom(models.Model):
    _name = 'sqa.stage1.bom'
    _description = 'SQA Stage 1 BOM Wizard'

    stage1_line_id = fields.Many2one('sqa.stage1.line', ondelete='cascade')
    bom_id = fields.Many2one('mrp.bom', string='BOM / Product', required=True, readonly=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    bom_line_ids = fields.One2many('sqa.stage1.bom.line', 'stage1_bom_id', string='Component Lines')
    total_cost = fields.Float(compute='_compute_totals', store=True, string='Total Cost Price')
    total_sales = fields.Float(compute='_compute_totals', store=True, string='Total Sales Price')

    @api.depends('bom_line_ids.product_qty', 'bom_line_ids.cost_price', 'bom_line_ids.sales_price')
    def _compute_totals(self):
        for rec in self:
            rec.total_cost = sum(l.product_qty * l.cost_price for l in rec.bom_line_ids)
            rec.total_sales = sum(l.product_qty * l.sales_price for l in rec.bom_line_ids)

    def action_save_and_close(self):
        return {'type': 'ir.actions.act_window_close'}


# ── sqa.stage1.bom.line ──────────────────────────────────────────────────────
class SqaStage1BomLine(models.Model):
    _name = 'sqa.stage1.bom.line'
    _description = 'SQA Stage 1 BOM Component Line'

    stage1_bom_id = fields.Many2one('sqa.stage1.bom', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Component', required=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    cost_price = fields.Float(string='Cost Price')
    sales_price = fields.Float(string='Sales Price')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.cost_price = self.product_id.standard_price
            self.sales_price = self.product_id.list_price
