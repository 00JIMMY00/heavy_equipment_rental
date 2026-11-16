// Keep employee creation short; the full form retains normal ERPNext fields.
frappe.ui.form.EmployeeQuickEntryForm = class EmployeeQuickEntryForm extends frappe.ui.form.QuickEntryForm {
    set_meta_and_mandatory_fields() {
        super.set_meta_and_mandatory_fields();
        const fields = ["first_name", "date_of_birth", "status", "date_of_joining"];
        // Native user/company defaults supply Company. Ask only if none is available.
        if (!this.doc.company) fields.push("company");
        this.mandatory = fields.map(name => ({...this.meta.fields.find(df => df.fieldname === name)}));
        this.mandatory[0].label = __("Employee Name");
        this.doc.gender = this.doc.gender || "Male";
    }
};
