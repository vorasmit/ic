const DOCTYPE = "Sales Invoice";
setup_e_waybill_actions(DOCTYPE);

frappe.ui.form.on(DOCTYPE, {
    setup(frm) {
        frm.set_query("transporter", {
            filters: {
                is_transporter: 1,
            },
        });

        frm.set_query("driver", doc => {
            return {
                filters: {
                    transporter: doc.transporter,
                },
            };
        });

        frm.set_query("port_address", {
            filters: {
                country: "India",
            },
        });
    },

    before_submit(frm) {
        frm.doc._submitted_from_ui = 1;
    },

    refresh(frm) {
        set_e_waybill_status_options(frm);
        gst_invoice_warning(frm);

        if (!(gst_settings.enable_e_waybill || gst_settings.enable_e_invoice)) return;
        show_sandbox_mode_indicator();
    },

    after_save(frm) {
        if (
            frm.doc.customer_address ||
            frm.doc.is_return ||
            frm.doc.is_debit_note ||
            !has_e_waybill_threshold_met(frm) ||
            !is_e_waybill_applicable(frm)
        )
            return;

        frappe.show_alert(
            {
                message: __("Billing Address is required to create e-Waybill"),
                indicator: "yellow",
            },
            10
        );
    },

    is_reverse_charge(frm) {
        india_compliance.toggle_and_set_supply_liable_to(frm)

    },
    ecommerce_gstin(frm) {
        india_compliance.toggle_and_set_supply_liable_to(frm)
    }
});

async function gst_invoice_warning(frm) {
    if (is_gst_invoice(frm) && !(await contains_gst_account(frm))) {
        frm.dashboard.add_comment(
            __(
                `GST is applicable for this invoice but no tax accounts specified in <a href="/app/gst-settings">
                GST Settings</a> are charged.`
            ),
            "red",
            true
        );
    }
}

function set_e_waybill_status_options(frm) {
    const options = ["Pending", "Not Applicable"];
    if (!options.includes(frm.doc.e_waybill_status)) {
        options.push(frm.doc.e_waybill_status);
    }
    set_field_options("e_waybill_status", options);
}

function is_gst_invoice(frm) {
    const gst_invoice_conditions =
        !frm.is_dirty() &&
        frm.doc.is_opening != "Yes" &&
        frm.doc.company_gstin &&
        frm.doc.company_gstin != frm.doc.billing_address_gstin &&
        frm.doc.items.some(item =>
            ["Taxable", "Zero-Rated"].includes(item.gst_treatment)
        );

    if (frm.doc.items[0].gst_treatment === "Zero-Rated")
        return gst_invoice_conditions && frm.doc.is_export_with_gst;
    else return gst_invoice_conditions;
}

async function contains_gst_account(frm) {
    const gst_accounts = await _get_account_options(frm.doc.company);
    const accounts = frm.doc.taxes.map(taxes => taxes.account_head);

    return accounts.some(account => gst_accounts.includes(account));
}

async function _get_account_options(company) {
    if (!frappe.flags.gst_accounts) {
        frappe.flags.gst_accounts = {};
    }

    if (!frappe.flags.gst_accounts[company]) {
        frappe.flags.gst_accounts[company] = await india_compliance.get_account_options(
            company
        );
    }

    return frappe.flags.gst_accounts[company];
}

function set_supply_liable_to(frm) {
    if (frm.doc.is_reverse_charge) {
        frm.set_value("supply_liable_to", "Reverse Charge u/s 9(5)")
    }
    else {
        frm.set_value("supply_liable_to", "Collect Tax u/s 52")
    }
}