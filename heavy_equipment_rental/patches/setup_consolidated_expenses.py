"""Seed company-specific عام defaults without replacing any user selection."""
import frappe


def execute():
    from heavy_equipment_rental.consolidated_expenses_setup import seed_defaults, update_workspace
    seed_defaults()
    update_workspace()
