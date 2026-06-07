from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SqaFinalStage(models.Model):
    _name = 'sqa.finalstage'
    _description = 'SQA Final Stage - Comparison & Approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New')
    )
    pre_order_ref_id = fields.Many2one(
        'sqa.stage1', string='Pre-Order Ref',
        domain=[('state', '=', 'checked')],
        required=True, tracking=True,
    )
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)

    # Stage 1 summary
    stage1_id = fields.Many2one('sqa.stage1', string='Stage 1', readonly=True)
    stage1_grand_cost  = fields.Float(string='S1 Grand Total Cost',  readonly=True)
    stage1_grand_sales = fields.Float(string='S1 Grand Total Sales', readonly=True)
    stage1_expected_profit = fields.Float(
        string='S1 Expected Profit', compute='_compute_profits', store=True
    )

    # Stage 2 summary
    stage2_id = fields.Many2one('sqa.stage2', string='Stage 2', readonly=True)
    stage2_grand_cost  = fields.Float(string='S2 Grand Total Cost',  readonly=True)
    stage2_grand_sales = fields.Float(string='S2 Grand Total Sales', readonly=True)
    stage2_expected_profit = fields.Float(
        string='S2 Expected Profit', compute='_compute_profits', store=True
    )

    # Stage 3 summary
    stage3_id = fields.Many2one('sqa.stage3', string='Stage 3', readonly=True)
    stage3_grand_cost  = fields.Float(string='S3 Grand Total Cost',  readonly=True)
    stage3_grand_sales = fields.Float(string='S3 Grand Total Sales', readonly=True)
    stage3_expected_profit = fields.Float(
        string='S3 Expected Profit', compute='_compute_profits', store=True
    )

    quotation_approval = fields.Selection(
        [('stage1', 'Stage 1'), ('stage2', 'Stage 2'), ('stage3', 'Stage 3')],
        string='Quotation Approval', tracking=True,
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved')],
        string='State', default='draft', tracking=True,
    )
    sale_order_id = fields.Many2one('sale.order', string='Sales Quotation', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sqa.finalstage') or _('New')
        return super().create(vals_list)

    @api.onchange('pre_order_ref_id')
    def _onchange_pre_order_ref_id(self):
        if not self.pre_order_ref_id:
            return
        s1 = self.pre_order_ref_id
        self.partner_id       = s1.partner_id.id
        self.stage1_id        = s1.id
        self.stage1_grand_cost  = s1.grand_total_cost
        self.stage1_grand_sales = s1.grand_total_sales

        s2 = s1.stage2_id
        if s2:
            self.stage2_id        = s2.id
            self.stage2_grand_cost  = s2.grand_total_cost
            self.stage2_grand_sales = s2.grand_total_sales

            s3 = s2.stage3_id
            if s3:
                self.stage3_id        = s3.id
                self.stage3_grand_cost  = s3.grand_total_cost
                self.stage3_grand_sales = s3.grand_total_sales

    @api.depends(
        'stage1_grand_cost', 'stage1_grand_sales',
        'stage2_grand_cost', 'stage2_grand_sales',
        'stage3_grand_cost', 'stage3_grand_sales',
    )
    def _compute_profits(self):
        for rec in self:
            rec.stage1_expected_profit = rec.stage1_grand_sales - rec.stage1_grand_cost
            rec.stage2_expected_profit = rec.stage2_grand_sales - rec.stage2_grand_cost
            rec.stage3_expected_profit = rec.stage3_grand_sales - rec.stage3_grand_cost

    def _get_approved_lines(self):
        self.ensure_one()
        mapping = {
            'stage1': self.stage1_id.sqa_stage1_line_ids if self.stage1_id else [],
            'stage2': self.stage2_id.sqa_stage2_line_ids if self.stage2_id else [],
            'stage3': self.stage3_id.sqa_stage3_line_ids if self.stage3_id else [],
        }
        return mapping.get(self.quotation_approval, [])

    def action_approve(self):
        for rec in self:
            employee = self.env.user.employee_id
            if not employee or employee.sqa_role != 's4':
                raise UserError(_('Only Management Team members (SQA Role = S4) can approve.'))
            if rec.state == 'approved':
                raise UserError(_('Already approved.'))
            if not rec.quotation_approval:
                raise UserError(_('Please select which stage to approve.'))

            approved_lines = rec._get_approved_lines()
            if not approved_lines:
                raise UserError(_('No BOM lines found for the selected approval stage.'))

            # ── 1. Create Sales Quotation ──────────────────────
            order_lines = []
            for line in approved_lines:
                unit_price = (line.total_sales / line.product_qty) if line.product_qty else 0.0
                product = line.bom_id.product_id or line.bom_id.product_tmpl_id.product_variant_ids[:1]
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': line.product_qty,
                    'price_unit': unit_price,
                    'name': product.display_name,
                }))
            sale_order = self.env['sale.order'].create({
                'partner_id': rec.partner_id.id,
                'order_line': order_lines,
                'origin': rec.name,
            })
            rec.sale_order_id = sale_order.id
            rec.message_post(body=_('Sales Quotation created: %s') % sale_order.name)

            # ── 2. Create Manufacturing Orders ─────────────────
            for line in approved_lines:
                product = line.bom_id.product_id or line.bom_id.product_tmpl_id.product_variant_ids[:1]
                mo = self.env['mrp.production'].create({
                    'product_id': product.id,
                    'product_qty': line.product_qty,
                    'bom_id': line.bom_id.id,
                    'origin': rec.name,
                })
                rec.message_post(body=_('Manufacturing Order created: %s') % mo.name)

            rec.state = 'approved'
        return True
