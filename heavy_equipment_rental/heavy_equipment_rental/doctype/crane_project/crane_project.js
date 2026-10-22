frappe.ui.form.on("Crane Project", {
    refresh(frm) {
        frm.set_intro(__("Historical record. New rentals start with a Crane Assignment or Crane Timesheet."));
    },
});
