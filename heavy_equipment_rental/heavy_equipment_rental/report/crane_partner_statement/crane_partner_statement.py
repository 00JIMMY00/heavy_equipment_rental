from heavy_equipment_rental.partner_reporting import execute_report


def execute(filters=None):
    return execute_report(filters, summary=False)
