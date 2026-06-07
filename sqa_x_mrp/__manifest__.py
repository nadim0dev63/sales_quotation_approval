{
    'name': 'Sales Quotation Approval Before Manufacturing',
    'version': '19.0.1.0.0',
    'category': 'presales',
    'summary': 'Multi-stage BOM costing and approval workflow before sales quotation',
    'description': """
        This module introduces a multi-stage costing and approval workflow that must
        be completed before a Sales Quotation is created and Manufacturing Orders
        are generated. Three teams independently estimate Bill of Materials (BOM)
        costs and sales prices. A management team then reviews all estimates,
        selects the best one, and triggers automatic creation of the Sales
        Quotation followed by Manufacturing Orders using the approved BOM.
    """,
    'author': 'Md. Nadim Hossain',
    'website': 'https://www.betopiagroup.com/',
    'depends': ['mrp', 'sale_management', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/hr_employee_views.xml',
        'views/mrp_bom_views.xml',
        'views/sqa_stage1_views.xml',
        'views/sqa_stage2_views.xml',
        'views/sqa_stage3_views.xml',
        'views/sqa_finalstage_views.xml',
        'views/menus.xml',
        'report/sqa_report_templates.xml',
        'report/sqa_report_actions.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}