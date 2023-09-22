# Copyright (c) 2023, Resilient Tech and contributors
# For license information, please see license.txt

from pypika.terms import Case

import frappe
from frappe import _
from frappe.query_builder import Criterion
from frappe.query_builder.functions import Sum
from frappe.utils import getdate

from india_compliance.gst_india.utils import get_gst_accounts_by_type


def execute(filters=None):
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "payment_entry",
            "label": _("Payment Entry"),
            "fieldtype": "Link",
            "options": "Payment Entry",
            "width": 180,
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150,
        },
        {
            "fieldname": "customer_name",
            "label": _("Customer Name"),
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "fieldname": "paid_amount",
            "label": _("Paid Amount"),
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "total_allocated_amount",
            "label": _("Allocated Amount"),
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "gst_paid",
            "label": _("GST Paid"),
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "gst_allocated",
            "label": _("GST Allocated"),
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "against_voucher",
            "label": _("Against Voucher"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 150,
        },
        {
            "fieldname": "place_of_supply",
            "label": _("Place of Supply"),
            "fieldtype": "Data",
            "width": 150,
        },
    ]


def get_data(filters):
    data = []
    advance_entries = get_gst_advance_details(filters)

    payment_enties = []

    for entry in advance_entries:
        row = frappe._dict()
        row.update(entry)

        if entry.payment_entry in payment_enties and entry.gst_allocated:
            row.update({"gst_paid": 0, "paid_amount": 0})

            if entry.paid_amount == entry.total_allocated_amount:
                row["total_allocated_amount"] = 0

        payment_enties.append(entry.payment_entry)
        data.append(row)

    return data


def get_gst_advance_details(filters):
    gst_accounts = get_gst_accounts(filters)

    gl_entry = frappe.qb.DocType("GL Entry")
    pe = frappe.qb.DocType("Payment Entry")

    conditions = get_conditions(filters, gl_entry, pe)

    gst_paid_column = Sum(
        Case()
        .when(
            gl_entry.account.isin(gst_accounts),
            gl_entry.credit_in_account_currency,
        )
        .else_(0)
    ).as_("gst_paid")

    gst_allocated_column = Sum(
        Case()
        .when(
            gl_entry.account.isin(gst_accounts),
            gl_entry.debit_in_account_currency,
        )
        .else_(0)
    ).as_("gst_allocated")

    query = (
        frappe.qb.from_(gl_entry)
        .join(pe)
        .on(pe.name == gl_entry.voucher_no)
        .select(
            gl_entry.posting_date,
            pe.name.as_("payment_entry"),
            pe.party.as_("customer"),
            pe.party_name.as_("customer_name"),
            pe.paid_amount,
            pe.total_allocated_amount,
            gst_paid_column,
            gst_allocated_column,
            gl_entry.against_voucher,
            pe.place_of_supply,
        )
        .where(Criterion.all(conditions))
    )

    query = query.groupby(gl_entry.posting_date, gl_entry.voucher_no)
    taxes = query.run(as_dict=True)

    return taxes


def get_conditions(filters, gl_entry, pe):
    company = filters.get("company")

    conditions = []

    conditions.append(gl_entry.is_cancelled == 0)
    conditions.append(gl_entry.voucher_type == "Payment Entry")
    conditions.append(pe.unallocated_amount.isnotnull())
    conditions.append(pe.total_taxes_and_charges.isnotnull())
    conditions.append(gl_entry.company == company)

    if filters.get("customer"):
        conditions.append(gl_entry.party == filters.get("customer"))

    if filters.get("account"):
        conditions.append(pe.paid_from == filters.get("account"))

    if filters.get("show_for_period") and filters.get("from_date"):
        conditions.append(gl_entry.posting_date >= getdate(filters.get("from_date")))

    if filters.get("to_date"):
        conditions.append(gl_entry.posting_date <= getdate(filters.get("to_date")))

    return conditions


def get_gst_accounts(filters):
    gst_accounts = get_gst_accounts_by_type(filters.get("company"), "Output")

    if not gst_accounts:
        return []

    return [account_head for type, account_head in gst_accounts.items()]
