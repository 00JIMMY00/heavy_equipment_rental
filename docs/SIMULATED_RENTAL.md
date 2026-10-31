# Simulated crane rental cycle

Created on `cranes-dev2.arab-erp.com` for `cranes company` in EGP. All records marked
**HER DEMO** are simulated, but their submitted documents post normal development-site
accounting entries. No live site was populated.

The owned 50-ton crane works 25–27 October 2026, 08:00–16:00 each day: 24 hours,
billed as 3 days × EGP 5,000.

| Record | Development-site ID |
| --- | --- |
| Customer | HER DEMO Rental Customer |
| Crane | CR-00058 |
| Assignment | ASG-00065 |
| Submitted Timesheet | TS-00051 |
| Submitted Sales Invoice | ACC-SINV-2026-00011 |
| Customer receipt, EGP 15,000 | ACC-PAY-2026-00002 |
| Custody funding, EGP 3,000 | TRE-2026-00002 |
| Cash fuel expense, EGP 1,500 | EXPE-00005 |
| Cash transport expense, EGP 500 | EXPE-00006 |
| Custody operator allowance, EGP 1,200 | EXPE-00007 |
| Custody site supplies, EGP 300 | EXPE-00008 |

The separate company accounts **HER Demo Cash - CC** and **HER Demo Driver Custody - CC**
have matching payment modes. Custody is represented by a separate cash asset account. The
operator is also linked as Employee on expenses. Funding custody transfers money between
accounts; it does not recognize a cost. Expenses consume EGP 1,500 of the EGP 3,000 custody,
leaving EGP 1,500. Demo cash retains EGP 10,000 after custody funding and cash expenses.

Open **Crane Operations → Rental Profitability** with Company `cranes company`,
From Date `2026-10-25`, To Date `2026-10-27`, and Assignment `ASG-00065`:

| Metric | EGP |
| --- | ---: |
| Total Income | 15,000 |
| Cash expenses | 2,000 |
| Custody expenses | 1,500 |
| Total Expenses | 3,500 |
| Net Sales (Income − Expenses) | 11,500 |

The report's expense rows show each source account. It includes supplier invoice costs for
rented cranes too; this particular example uses an owned crane and has no supplier hire cost.

## Repeatable creation

Only run this explicitly on a development site as a System Manager, after migration:

```bash
bench --site cranes-dev2.arab-erp.com execute heavy_equipment_rental.demo.create_rental_cycle --kwargs '{"company":"cranes company","start_date":"2026-10-25"}'
```

The command uses normal document validation and submission, rolls back its changes on failure,
and returns the existing cycle for the same company and demo location on repeat calls. It does
not overwrite or reset a previously created cycle. It creates its own customer, operator, crane,
accounts, payment modes, and expense types. The company's accounting defaults, customer group,
territory, service item group, and fiscal year must already be configured. Nothing is created
automatically on installation or migration.
