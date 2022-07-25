frappe.provide("ic");

class _Filter extends frappe.ui.Filter {
    set_conditions_from_config() {
        if (this.filter_list.filter_options) {
            Object.assign(this, this.filter_list.filter_options);
        }
    }
}

ic.FilterGroup = class FilterGroup extends frappe.ui.FilterGroup {
    _push_new_filter(...args) {
        const Filter = frappe.ui.Filter;
        try {
            frappe.ui.Filter = _Filter;
            return super._push_new_filter(...args);
        } finally {
            frappe.ui.Filter = Filter;
        }
    }
};
