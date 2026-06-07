from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sqa_role = fields.Selection(
        selection=[
            ('s1', 'S1 - Initial Costing'),
            ('s2', 'S2 - Partial Review'),
            ('s3', 'S3 - Final Costing'),
            ('s4', 'S4 - Management'),
        ],
        string='SQA Role',
        help='Determines which SQA stage check/approve button is visible'
    )