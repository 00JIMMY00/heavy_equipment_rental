from frappe import _


def get_data():
    return {
        'fieldname': 'crane_maintenance',
        'internal_links': {'Crane': 'crane', 'Crane Assignment': 'crane_assignment',
            'Crane Timesheet': 'crane_timesheet', 'Payment Entry': 'repair_payment_entry'},
        'transactions': [
            {'label': _('Stock and Accounting'), 'items': ['Stock Entry', 'Purchase Invoice',
                'Sales Invoice', 'Asset Repair', 'Expense Entry', 'Payment Entry']},
            {'label': _('Rental'), 'items': ['Crane', 'Crane Assignment', 'Crane Timesheet']},
        ],
    }
