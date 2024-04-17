# Copyright (c) 2024, Resilient Tech and contributors
# For license information, please see license.txt
import gzip
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date

DOCTYPE = "GSTR-1 Filed Log"


class GSTR1FiledLog(Document):

    @property
    def status(self):
        return self.generation_status

    def update_status(self, status):
        self.db_set("generation_status", status)

    def show_report(self):
        # TODO: Implement
        pass

    # FILE UTILITY
    def load_data(self):
        data = {}
        file_fields = self.get_applicable_file_fields()

        for file_field in file_fields:
            if json_data := self.get_json_for(file_field):
                data[file_field] = json_data

        return data

    def get_json_for(self, file_field):
        if file := get_file_doc(self.name, file_field):
            return get_decompressed_data(file.get_content())

    def update_json_for(self, file_field, json_data, overwrite=True):
        # existing file
        if file := get_file_doc(self.name, file_field):
            if overwrite:
                new_json = json_data
            else:
                new_json = get_decompressed_data(file.get_content())
                new_json.update(json_data)

            content = get_compressed_data(new_json)

            file.save_file(content=content, overwrite=True)
            self.db_set(file_field, file.file_url)
            return

        # new file
        content = get_compressed_data(json_data)
        file_name = frappe.scrub("{0}-{1}.json.gz".format(self.name, file_field))
        file = frappe.get_doc(
            {
                "doctype": "File",
                "attached_to_doctype": DOCTYPE,
                "attached_to_name": self.name,
                "attached_to_field": file_field,
                "file_name": file_name,
                "is_private": 1,
                "content": content,
            }
        ).insert()
        self.db_set(file_field, file.file_url)

    # GSTR 1 UTILITY
    def is_sek_needed(self, settings=None):
        if not settings:
            settings = frappe.get_cached_doc("GST Settings")

        if not settings.analyze_filed_data:
            return False

        if not self.e_invoice_data or self.filing_status != "Filed":
            return True

        if not self.filed_gstr1:
            return True

        return False

    def is_sek_valid(self, settings=None):
        if not settings:
            settings = frappe.get_cached_doc("GST Settings")

        for credential in settings.credentials:
            if credential.service == "Returns" and credential.gstin == self.gstin:
                break

        else:
            frappe.throw(
                _("No credential found for the GSTIN {0} in the GST Settings").format(
                    self.gstin
                )
            )

        if credential.session_expiry and credential.session_expiry > add_to_date(
            None, minutes=-30
        ):
            return True

    def has_all_files(self, settings=None):
        if not self.is_latest_data:
            return False

        file_fields = self.get_applicable_file_fields(settings)
        return all(getattr(self, file_field) for file_field in file_fields)

    def get_applicable_file_fields(self, settings=None):
        if not settings:
            settings = frappe.get_cached_doc("GST Settings")

        fields = ["computed_gstr1", "computed_gstr1_summary"]

        if settings.analyze_filed_data:
            fields.extend(["reconciled_gstr1", "reconciled_gstr1_summary"])

            if self.filing_status == "Filed":
                fields.extend(["filed_gstr1", "filed_gstr1_summary"])
            else:
                fields.extend(["e_invoice_data", "e_invoice_summary"])

        return fields


def process_gstr_1_returns_info(gstin, response):
    return_info = {}

    # compile gstr-1 returns info
    for info in response.get("EFiledlist"):
        if info["rtntype"] == "GSTR1":
            return_info[f"{info['ret_prd']}-{gstin}"] = info

    # existing filed logs
    filed_logs = frappe._dict(
        frappe.get_all(
            "GSTR-1 Filed Log",
            filters={"name": ("in", list(return_info.keys()))},
            fields=["name", "filing_status"],
            as_list=1,
        )
    )

    # create or update filed logs
    for key, info in return_info.items():
        filing_details = {
            "filing_status": info["status"],
            "acknowledgement_number": info["arn"],
            "filing_date": datetime.strptime(info["dof"], "%d-%m-%Y").date(),
        }

        if key in filed_logs:
            if filed_logs[key] != info["status"]:
                frappe.db.set_value("GSTR-1 Filed Log", key, filing_details)

            continue

        frappe.get_doc(
            {
                "doctype": "GSTR-1 Filed Log",
                "gstin": gstin,
                "return_period": info["ret_prd"],
                **filing_details,
            }
        ).insert()


def get_file_doc(gstr1_log_name, attached_to_field):
    try:
        return frappe.get_doc(
            "File",
            {
                "attached_to_doctype": DOCTYPE,
                "attached_to_name": gstr1_log_name,
                "attached_to_field": attached_to_field,
            },
        )

    except frappe.DoesNotExistError:
        return None


def get_compressed_data(json_data):
    return gzip.compress(frappe.safe_encode(frappe.as_json(json_data)))


def get_decompressed_data(content):
    return frappe.parse_json(frappe.safe_decode(gzip.decompress(content)))
