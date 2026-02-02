# Copyright (c) 2026, Resilient Tech and contributors
# For license information, please see license.txt

import json
import os

import frappe


def execute():
    """
    Patch to sync Schedule III financial report templates and update existing
    accounts with account categories based on India chart of accounts mapping.
    """
    sync_financial_report_templates()
    update_account_categories_for_india()


def sync_financial_report_templates():
    """Sync financial report templates including Schedule III templates."""
    from erpnext.accounts.doctype.financial_report_template.financial_report_template import (
        sync_financial_report_templates as sync_templates,
    )

    sync_templates()


def update_account_categories_for_india():
    """Update existing accounts with account categories based on India chart mapping."""
    account_mapping = get_india_account_category_mapping()
    if not account_mapping:
        return

    companies = frappe.get_all(
        "Company",
        filters={"country": "India"},
        pluck="name",
    )

    mapped_account_categories = {}

    for company in companies:
        map_account_categories_for_company(
            company, account_mapping, mapped_account_categories
        )

    if not mapped_account_categories:
        return

    frappe.db.bulk_update("Account", mapped_account_categories)


def get_india_account_category_mapping():
    """Extract account category mapping from India chart of accounts."""
    chart_path = os.path.join(
        frappe.get_app_path("erpnext"),
        "accounts",
        "doctype",
        "account",
        "chart_of_accounts",
        "verified",
        "in_standard_chart_of_accounts.json",
    )

    if not os.path.exists(chart_path):
        return {}

    with open(chart_path) as f:
        chart_data = json.load(f)

    account_mapping = {}
    _extract_account_mapping(chart_data.get("tree", {}), account_mapping)

    return account_mapping


def _extract_account_mapping(chart_data, account_mapping):
    """Recursively extract account name to category mapping from chart tree."""
    metadata_fields = {"root_type", "account_type", "account_category", "is_group"}

    for account_name, account_details in chart_data.items():
        if account_name in metadata_fields:
            continue

        if isinstance(account_details, dict):
            if account_details.get("account_category"):
                account_mapping[account_name] = account_details["account_category"]

            _extract_account_mapping(account_details, account_mapping)


def map_account_categories_for_company(
    company, account_mapping, mapped_account_categories
):
    """Map account categories for a specific company."""
    accounts = frappe.get_all(
        "Account",
        filters={"company": company, "account_category": ["is", "not set"]},
        fields=["name", "account_name"],
    )

    for account in accounts:
        account_category = account_mapping.get(account.account_name)

        if account_category:
            mapped_account_categories[account.name] = {
                "account_category": account_category
            }
