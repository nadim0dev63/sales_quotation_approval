from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SqaFinalStage(models.Model):
    _name = 'sqa.finalstage'
    _description = 'SQA Final Stage - Comparison & Approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    pre_order_ref_id = fields.Many2one(
        'sqa.stage1', string='Pre-Order Ref',
        domain=[('state', '=', 'checked')],
        required=True, tracking=True,
    )
    # The human-readable pre-order ref string (e.g. SQA00001) from stage1
    pre_order_ref = fields.Char(
        string='Pre-Order Reference',
        compute='_compute_from_pre_order_ref',
        store=True,
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer',
        compute='_compute_from_pre_order_ref', store=True,
    )

    # ── Stage references (all computed+stored so they survive save) ──────────
    stage1_id = fields.Many2one(
        'sqa.stage1',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage1_grand_cost = fields.Float(
        string='S1 Grand Total Cost',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage1_grand_sales = fields.Float(
        string='S1 Grand Total Sales',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage1_expected_profit = fields.Float(
        compute='_compute_profits', store=True, string='S1 Expected Profit',
    )

    stage2_id = fields.Many2one(
        'sqa.stage2',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage2_grand_cost = fields.Float(
        string='S2 Grand Total Cost',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage2_grand_sales = fields.Float(
        string='S2 Grand Total Sales',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage2_expected_profit = fields.Float(
        compute='_compute_profits', store=True, string='S2 Expected Profit',
    )

    stage3_id = fields.Many2one(
        'sqa.stage3',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage3_grand_cost = fields.Float(
        string='S3 Grand Total Cost',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage3_grand_sales = fields.Float(
        string='S3 Grand Total Sales',
        compute='_compute_from_pre_order_ref', store=True,
    )
    stage3_expected_profit = fields.Float(
        compute='_compute_profits', store=True, string='S3 Expected Profit',
    )

    # ── BOM line mirrors (computed, for the 3 notebook tabs) ────────────────
    stage1_line_ids = fields.One2many(
        'sqa.stage1.line', compute='_compute_stage_lines', string='S1 BOM Lines',
    )
    stage2_line_ids = fields.One2many(
        'sqa.stage2.line', compute='_compute_stage_lines', string='S2 BOM Lines',
    )
    stage3_line_ids = fields.One2many(
        'sqa.stage3.line', compute='_compute_stage_lines', string='S3 BOM Lines',
    )

    quotation_approval = fields.Selection(
        [('stage1', 'Stage 1'), ('stage2', 'Stage 2'), ('stage3', 'Stage 3')],
        string='Quotation Approval', tracking=True,
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved')],
        default='draft', tracking=True,
    )
    sale_order_id = fields.Many2one('sale.order', string='Sales Quotation', readonly=True, copy=False)

    # ── Sequence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sqa.finalstage') or _('New')
        return super().create(vals_list)

    # ── Single compute that derives everything from pre_order_ref_id ─────────
    @api.depends(
        'pre_order_ref_id',
        'pre_order_ref_id.grand_total_cost',
        'pre_order_ref_id.grand_total_sales',
        'pre_order_ref_id.stage2_id',
        'pre_order_ref_id.stage2_id.grand_total_cost',
        'pre_order_ref_id.stage2_id.grand_total_sales',
        'pre_order_ref_id.stage2_id.stage3_id',
        'pre_order_ref_id.stage2_id.stage3_id.grand_total_cost',
        'pre_order_ref_id.stage2_id.stage3_id.grand_total_sales',
        'pre_order_ref_id.state',  # Add dependency on state
        'pre_order_ref_id.stage2_id.state',  # Add dependency on stage2 state
        'pre_order_ref_id.stage2_id.stage3_id.state',  # Add dependency on stage3 state
    )
    def _compute_from_pre_order_ref(self):
        for rec in self:
            s1 = rec.pre_order_ref_id
            if not s1:
                rec.pre_order_ref = False
                rec.partner_id = False
                rec.stage1_id = False
                rec.stage1_grand_cost = 0.0
                rec.stage1_grand_sales = 0.0
                rec.stage2_id = False
                rec.stage2_grand_cost = 0.0
                rec.stage2_grand_sales = 0.0
                rec.stage3_id = False
                rec.stage3_grand_cost = 0.0
                rec.stage3_grand_sales = 0.0
                continue

            rec.pre_order_ref = s1.pre_order_ref   # the SQA00001 string
            rec.partner_id = s1.partner_id
            rec.stage1_id = s1
            rec.stage1_grand_cost = s1.grand_total_cost or 0.0
            rec.stage1_grand_sales = s1.grand_total_sales or 0.0

            s2 = s1.stage2_id
            rec.stage2_id = s2
            rec.stage2_grand_cost = s2.grand_total_cost or 0.0 if s2 else 0.0
            rec.stage2_grand_sales = s2.grand_total_sales or 0.0 if s2 else 0.0

            s3 = s2.stage3_id if s2 else False
            rec.stage3_id = s3
            rec.stage3_grand_cost = s3.grand_total_cost or 0.0 if s3 else 0.0
            rec.stage3_grand_sales = s3.grand_total_sales or 0.0 if s3 else 0.0

    @api.depends(
        'stage1_grand_cost', 'stage1_grand_sales',
        'stage2_grand_cost', 'stage2_grand_sales',
        'stage3_grand_cost', 'stage3_grand_sales',
        'pre_order_ref_id',  # Add this to recompute when pre_order_ref_id changes
        'stage1_id',  # Add this to ensure recomputation when stage1 changes
        'stage2_id',  # Add this to ensure recomputation when stage2 changes
        'stage3_id',  # Add this to ensure recomputation when stage3 changes
    )
    def _compute_profits(self):
        for rec in self:
            rec.stage1_expected_profit = (rec.stage1_grand_sales or 0.0) - (rec.stage1_grand_cost or 0.0)
            rec.stage2_expected_profit = (rec.stage2_grand_sales or 0.0) - (rec.stage2_grand_cost or 0.0)
            rec.stage3_expected_profit = (rec.stage3_grand_sales or 0.0) - (rec.stage3_grand_cost or 0.0)

    # ── Computed: pull BOM lines from linked stages ──────────────────────────
    @api.depends('stage1_id', 'stage2_id', 'stage3_id')
    def _compute_stage_lines(self):
        for rec in self:
            rec.stage1_line_ids = rec.stage1_id.sqa_stage1_line_ids if rec.stage1_id else self.env['sqa.stage1.line']
            rec.stage2_line_ids = rec.stage2_id.sqa_stage2_line_ids if rec.stage2_id else self.env['sqa.stage2.line']
            rec.stage3_line_ids = rec.stage3_id.sqa_stage3_line_ids if rec.stage3_id else self.env['sqa.stage3.line']

    # ── Override write to ensure recomputation on save ────────────────────────
    def write(self, vals):
        # If pre_order_ref_id is being changed or if we're saving without changes,
        # force recomputation of related fields
        result = super().write(vals)
        if 'pre_order_ref_id' in vals or not vals:
            # Trigger recomputation by modifying a non-stored computed field
            self.modified(['stage1_expected_profit', 'stage2_expected_profit', 'stage3_expected_profit'])
        return result

    # ── Override read to ensure values are computed before reading ────────────
    @api.model
    def read(self, fields=None, load='_classic_read'):
        # Ensure computed fields are up to date
        if self:
            self._compute_from_pre_order_ref()
            self._compute_profits()
            self._compute_stage_lines()
        return super().read(fields=fields, load=load)

    # ── Approve ──────────────────────────────────────────────────────────────
    def action_approve(self):
        self.ensure_one()
        employee = self.env.user.employee_id
        if not employee or employee.sqa_role != 's4':
            raise UserError(_('Only SQA Role S4 (Management) can approve.'))
        if self.state == 'approved':
            raise UserError(_('Already approved.'))
        if not self.quotation_approval:
            raise UserError(_('Please select which stage to approve.'))

        s1 = self.pre_order_ref_id
        s2 = s1.stage2_id
        s3 = s2.stage3_id if s2 else self.env['sqa.stage3']

        approved_lines = {
            'stage1': s1.sqa_stage1_line_ids,
            'stage2': s2.sqa_stage2_line_ids if s2 else self.env['sqa.stage2.line'],
            'stage3': s3.sqa_stage3_line_ids if s3 else self.env['sqa.stage3.line'],
        }.get(self.quotation_approval, self.env['sqa.stage1.line'])

        if not approved_lines:
            raise UserError(_('No BOM lines found for the selected stage.'))

        order_lines = []
        for line in approved_lines:
            if not line.product_qty:
                continue
            # Prevent division by zero
            unit_price = line.total_sales / line.product_qty if line.product_qty else 0.0
            product = line.bom_id.product_id or line.bom_id.product_tmpl_id.product_variant_ids[:1]
            if not product:
                raise UserError(_('BOM "%s" has no product set.') % line.bom_id.display_name)
            order_lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': line.product_qty,
                'price_unit': unit_price,
                'name': product.display_name,
            }))

        sale_order = self.env['sale.order'].create({
            'partner_id': s1.partner_id.id,
            'order_line': order_lines,
            'origin': self.name,
        })
        self.sale_order_id = sale_order.id
        self.state = 'approved'
        self.message_post(body=_('Sales Quotation created: %s') % sale_order.name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }