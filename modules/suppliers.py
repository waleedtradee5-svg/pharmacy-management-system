import streamlit as st
import pandas as pd
from db_connector import fetch_data, execute_query


class SuppliersModule:
    """
    Manages Suppliers with full CRUD functionality, KPIs, and a premium UI.
    This module is self-contained and handles all supplier-related operations.
    """

    def __init__(self):
        """Initializes session state keys for handling UI interactions."""
        st.session_state.setdefault("editing_supplier_id", None)
        st.session_state.setdefault("confirm_delete_supplier_id", None)

    def _get_data(self):
        """Fetches supplier data from the database and calculates KPIs."""
        self.suppliers = fetch_data("SELECT * FROM suppliers ORDER BY SupplierName")

        if self.suppliers is not None and not self.suppliers.empty:
            self.kpi_total_suppliers = len(self.suppliers)
            self.kpi_active_suppliers = len(
                self.suppliers[self.suppliers["IsActive"] == 1]
            )
        else:
            self.kpi_total_suppliers = self.kpi_active_suppliers = 0

    def render(self):
        """
        Main render method.
        Decides whether to show the main list view or the add/edit form.
        """
        self._get_data()
        st.title("🚚 Supplier Management")

        if st.session_state.editing_supplier_id is not None:
            self._render_supplier_form(st.session_state.editing_supplier_id)
        else:
            self._render_main_view()

    def _render_main_view(self):
        """Renders the KPI cards, action buttons, and the list of suppliers."""
        # --- KPIs ---
        st.subheader("Supplier Overview")
        kpi_cols = st.columns(2)
        kpi_cols[0].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Total Suppliers</p><p class="kpi-value">{self.kpi_total_suppliers}</p></div>',
            unsafe_allow_html=True,
        )
        kpi_cols[1].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Active Suppliers</p><p class="kpi-value">{self.kpi_active_suppliers}</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        # --- Add Button and Header ---
        col1, col2 = st.columns([3, 1])
        col1.subheader("All Suppliers")
        if col2.button("➕ Add New Supplier", use_container_width=True):
            st.session_state.editing_supplier_id = "new"
            st.rerun()

        # --- Suppliers List ---
        if self.suppliers is not None and not self.suppliers.empty:
            for _, sup in self.suppliers.iterrows():
                self._render_supplier_row(sup)
        else:
            st.info("No suppliers found. Click 'Add New Supplier' to get started.")

    def _render_supplier_row(self, supplier):
        """Renders a single supplier's information in a row format."""
        st.markdown("---")
        row_cols = st.columns([3, 3, 2, 2])

        # Column 1: Name and Address
        row_cols[0].markdown(f"**{supplier['SupplierName']}**")
        row_cols[0].caption(f"📍 {supplier.get('Address', 'No address provided')}")

        # Column 2: Contact Info
        row_cols[1].markdown(f"📞 {supplier.get('Contact', 'N/A')}")
        row_cols[1].markdown(f"✉️ {supplier.get('Email', 'N/A')}")

        # Column 3: Status
        status_text = "Active" if supplier.get("IsActive") else "Inactive"
        status_class = "status-ok" if supplier.get("IsActive") else "status-low"
        row_cols[2].markdown(
            f"**Status:**<br><span class='status-tag {status_class}'>{status_text}</span>",
            unsafe_allow_html=True,
        )

        # Column 4: Action Buttons
        with row_cols[3]:
            action_cols = st.columns(2)
            if action_cols[0].button(
                "✏️", key=f"edit_sup_{supplier['SupplierID']}", help="Edit Supplier"
            ):
                st.session_state.editing_supplier_id = supplier["SupplierID"]
                st.rerun()
            if action_cols[1].button(
                "🗑️", key=f"del_sup_{supplier['SupplierID']}", help="Delete Supplier"
            ):
                st.session_state.confirm_delete_supplier_id = supplier["SupplierID"]
                st.rerun()

        # Handle the delete confirmation logic right after the row
        self._handle_delete_confirmation(supplier["SupplierID"])

    def _render_supplier_form(self, supplier_id):
        """Renders the form for adding or editing a supplier."""
        is_edit = supplier_id != "new"
        title = "Edit Supplier" if is_edit else "➕ Add New Supplier"

        supplier_data = {}
        if is_edit:
            supplier_data = (
                self.suppliers[self.suppliers["SupplierID"] == supplier_id]
                .iloc[0]
                .to_dict()
            )

        with st.form("supplier_form"):
            st.subheader(title)

            name = st.text_input(
                "Supplier Name*", value=supplier_data.get("SupplierName", "")
            )
            contact = st.text_input(
                "Contact Number", value=supplier_data.get("Contact", "")
            )
            email = st.text_input("Email Address", value=supplier_data.get("Email", ""))
            address = st.text_area(
                "Full Address", value=supplier_data.get("Address", "")
            )
            is_active = st.checkbox(
                "Is Active", value=bool(supplier_data.get("IsActive", True))
            )

            # --- Form Buttons ---
            submitted = st.form_submit_button("Save", type="primary")
            cancelled = st.form_submit_button("Cancel")

            if submitted:
                if not name:
                    st.error("Supplier Name is a required field.")
                else:
                    # Prepare params, ensuring correct Python types
                    params = (name, contact, email, address, bool(is_active))

                    if is_edit:
                        query = "UPDATE suppliers SET SupplierName=%s, Contact=%s, Email=%s, Address=%s, IsActive=%s WHERE SupplierID=%s"
                        # Convert numpy.int64 to standard Python int for the query
                        params += (int(supplier_id),)
                    else:
                        query = "INSERT INTO suppliers (SupplierName, Contact, Email, Address, IsActive) VALUES (%s, %s, %s, %s, %s)"

                    if execute_query(query, params):
                        st.success(
                            f"Supplier '{name}' was {'updated' if is_edit else 'added'} successfully!"
                        )
                        st.session_state.editing_supplier_id = None
                        st.rerun()

            if cancelled:
                st.session_state.editing_supplier_id = None
                st.rerun()

    def _handle_delete_confirmation(self, supplier_id):
        """Renders the confirmation dialog if a delete button was clicked."""
        if st.session_state.confirm_delete_supplier_id == supplier_id:
            st.warning(
                f"**Are you sure you want to delete this supplier?** This may affect related records."
            )

            confirm_cols = st.columns([1, 1, 5])
            if confirm_cols[0].button(
                "Yes, Delete", key=f"confirm_del_{supplier_id}", type="primary"
            ):
                if execute_query(
                    "DELETE FROM suppliers WHERE SupplierID=%s", (int(supplier_id),)
                ):
                    st.success("Supplier deleted successfully.")
                    st.session_state.confirm_delete_supplier_id = None
                    st.rerun()

            if confirm_cols[1].button("No, Cancel", key=f"cancel_del_{supplier_id}"):
                st.session_state.confirm_delete_supplier_id = None
                st.rerun()
