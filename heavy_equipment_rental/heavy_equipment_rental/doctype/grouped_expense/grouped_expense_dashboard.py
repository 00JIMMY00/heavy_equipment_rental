from frappe import _


def get_data():
    return {
        'fieldname': 'amended_from',
        'internal_links': {
            'Expense Entry': ['items', 'expense_entry'],
            'Journal Entry': ['items', 'journal_entry'],
            'Crane Maintenance': 'crane_maintenance', 'Crane': 'crane', 'Crane Timesheet': 'crane_timesheet',
            'Rental Contract': 'crane_assignment', 'Crane Profit Settlement': 'profit_settlement',
        },
        'transactions': [
            {'label': _('Rental'), 'items': ['Crane', 'Crane Timesheet', 'Rental Contract', 'Crane Maintenance']},
            {'label': _('Accounting'), 'items': ['Journal Entry', 'Expense Entry', 'Crane Profit Settlement']},
        ],
    }
