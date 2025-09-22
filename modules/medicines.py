import streamlit as st
import pandas as pd
from datetime import date, timedelta
from db_connector import fetch_data, execute_query


class MedicinesModule:
    """
    Manages Medicines with full CRUD functionality, KPIs, and a premium UI.
    """

    def __init__(self):
        """Initializes session state keys for handling UI interactions."""
        st.session_state.setdefault("editing_medicine_id", None)
        st.session_state.setdefault("viewing_kpi_list", None)
        st.session_state.setdefault("confirm_delete_medicine_id", None)

    def _get_data(self):
        """Fetches all necessary data from the database and calculates KPIs."""
        self.medicines = fetch_data(
            "SELECT m.*, s.SupplierName FROM medicines m LEFT JOIN suppliers s ON m.SupplierID = s.SupplierID ORDER BY m.MedicineName"
        )
        self.suppliers = fetch_data("SELECT * FROM suppliers ORDER BY SupplierName")

        if self.medicines is not None and not self.medicines.empty:
            self.medicines["ExpiryDate"] = pd.to_datetime(self.medicines["ExpiryDate"])
            self.kpi_total_medicines = len(self.medicines)
            self.low_stock_df = self.medicines[self.medicines["StockQty"] < 10]
            self.kpi_low_stock_count = len(self.low_stock_df)
            expiring_soon_date = pd.to_datetime("today") + timedelta(days=30)
            self.expiring_soon_df = self.medicines[
                self.medicines["ExpiryDate"] <= expiring_soon_date
            ]
            self.kpi_expiring_soon_count = len(self.expiring_soon_df)
            self.kpi_out_of_stock_count = len(
                self.medicines[self.medicines["StockQty"] == 0]
            )
        else:
            self.kpi_total_medicines = self.kpi_low_stock_count = (
                self.kpi_expiring_soon_count
            ) = self.kpi_out_of_stock_count = 0
            self.low_stock_df = self.expiring_soon_df = pd.DataFrame()

    def render(self):
        """Main render method that routes to the correct view (list or form)."""
        self._get_data()
        st.title("💊 Medicines Management")

        if st.session_state.editing_medicine_id is not None:
            self._render_medicine_form(st.session_state.editing_medicine_id)
        else:
            self._render_main_view()

    def _render_main_view(self):
        """Renders the main medicines view with KPIs and the list."""
        # --- KPIs ---
        kpi_cols = st.columns(4)
        kpi_cols[0].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Total Medicines</p><p class="kpi-value">{self.kpi_total_medicines}</p></div>',
            unsafe_allow_html=True,
        )
        with kpi_cols[1]:
            if st.button(
                "Low Stock (<10)", key="low_stock_kpi", use_container_width=True
            ):
                st.session_state.viewing_kpi_list = "low_stock"
                st.rerun()
            st.markdown(
                f'<div class="kpi-card" style="margin-top:-50px;"><p class="kpi-title">Low Stock (&lt;10)</p><p class="kpi-value">{self.kpi_low_stock_count}</p></div>',
                unsafe_allow_html=True,
            )
        with kpi_cols[2]:
            if st.button(
                "Expiring Soon (30d)", key="exp_soon_kpi", use_container_width=True
            ):
                st.session_state.viewing_kpi_list = "expiring_soon"
                st.rerun()
            st.markdown(
                f'<div class="kpi-card" style="margin-top:-50px;"><p class="kpi-title">Expiring Soon (30d)</p><p class="kpi-value">{self.kpi_expiring_soon_count}</p></div>',
                unsafe_allow_html=True,
            )
        kpi_cols[3].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Out of Stock</p><p class="kpi-value">{self.kpi_out_of_stock_count}</p></div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        if st.session_state.viewing_kpi_list:
            self._display_kpi_drilldown()
        else:
            self._display_all_medicines()

    def _display_kpi_drilldown(self):
        """Displays the filtered list when a KPI is clicked."""
        df, title = (
            (self.low_stock_df, "Medicines with Low Stock")
            if st.session_state.viewing_kpi_list == "low_stock"
            else (self.expiring_soon_df, "Medicines Expiring Soon")
        )
        st.subheader(title)
        if st.button("⬅️ Back to All Medicines"):
            st.session_state.viewing_kpi_list = None
            st.rerun()
        st.dataframe(df, use_container_width=True, hide_index=True)

    def _display_all_medicines(self):
        """Displays the main list of all medicines."""
        if st.button("➕ Add New Medicine"):
            st.session_state.editing_medicine_id = "new"
            st.rerun()
        if self.medicines is not None and not self.medicines.empty:
            for _, med in self.medicines.iterrows():
                self._render_medicine_row(med)

    def _render_medicine_row(self, medicine):
        """Renders a single medicine's information in a row format."""
        st.markdown("---")
        row_cols = st.columns([3, 2, 2, 2, 2])

        row_cols[0].markdown(
            f"**{medicine['MedicineName']}**<br><small>{medicine.get('Category', 'N/A')} | {medicine.get('Brand', 'N/A')}</small>",
            unsafe_allow_html=True,
        )
        stock_qty, status_class = (
            medicine["StockQty"],
            "status-ok" if medicine["StockQty"] >= 10 else "status-low",
        )
        row_cols[1].markdown(
            f"Stock: <span class='status-tag {status_class}'>{stock_qty}</span>",
            unsafe_allow_html=True,
        )

        exp_date = medicine["ExpiryDate"].date()
        days_left = (exp_date - date.today()).days
        exp_status_class = (
            "status-ok"
            if days_left > 30
            else ("status-expiring" if 0 <= days_left <= 30 else "status-low")
        )
        row_cols[2].markdown(
            f"Expiry: <span class='status-tag {exp_status_class}'>{exp_date.strftime('%b %d, %Y')}</span>",
            unsafe_allow_html=True,
        )

        row_cols[3].markdown(
            f"**Supplier**<br>{medicine.get('SupplierName', 'N/A')}",
            unsafe_allow_html=True,
        )

        with row_cols[4]:
            action_cols = st.columns(2)
            if action_cols[0].button(
                "✏️", key=f"edit_med_{medicine['MedicineID']}", help="Edit Medicine"
            ):
                st.session_state.editing_medicine_id = medicine["MedicineID"]
                st.rerun()
            if action_cols[1].button(
                "🗑️", key=f"del_med_{medicine['MedicineID']}", help="Delete Medicine"
            ):
                st.session_state.confirm_delete_medicine_id = medicine["MedicineID"]
                st.rerun()

        self._handle_delete_confirmation(medicine["MedicineID"])

    def _render_medicine_form(self, medicine_id):
        """Renders the form for adding or editing a medicine."""
        is_edit = medicine_id != "new"
        title = "Edit Medicine" if is_edit else "➕ Add New Medicine"

        medicine_data = {}
        if is_edit:
            medicine_data = (
                self.medicines[self.medicines["MedicineID"] == medicine_id]
                .iloc[0]
                .to_dict()
            )

        with st.form(key="medicine_form"):
            st.subheader(title)

            name = st.text_input(
                "Medicine Name*", value=medicine_data.get("MedicineName", "")
            )
            category = st.text_input(
                "Category", value=medicine_data.get("Category", "")
            )
            brand = st.text_input("Brand", value=medicine_data.get("Brand", ""))

            supplier_options = {
                s["SupplierName"]: s["SupplierID"] for _, s in self.suppliers.iterrows()
            }
            supplier_names = [""] + list(supplier_options.keys())
            current_supplier = medicine_data.get("SupplierName", "")
            supplier_idx = (
                supplier_names.index(current_supplier)
                if current_supplier in supplier_names
                else 0
            )
            selected_supplier_name = st.selectbox(
                "Supplier", supplier_names, index=supplier_idx
            )

            form_cols = st.columns(3)
            stock = form_cols[0].number_input(
                "Stock Qty*",
                value=int(medicine_data.get("StockQty", 0)),
                min_value=0,
                step=1,
            )
            unit_price = form_cols[1].number_input(
                "Selling Price*",
                value=float(medicine_data.get("UnitPrice", 0.0)),
                format="%.2f",
            )
            purchase_price = form_cols[2].number_input(
                "Purchase Price*",
                value=float(medicine_data.get("PurchasePrice", 0.0)),
                format="%.2f",
            )

            expiry_date = st.date_input(
                "Expiry Date",
                value=pd.to_datetime(
                    medicine_data.get("ExpiryDate", date.today() + timedelta(days=365))
                ).date(),
            )
            is_active = st.checkbox(
                "Is Active", value=bool(medicine_data.get("IsActive", True))
            )

            submitted = st.form_submit_button("Save", type="primary")
            cancelled = st.form_submit_button("Cancel")

            if submitted:
                if not name:
                    st.error("Medicine Name is a required field.")
                else:
                    supplier_id = supplier_options.get(selected_supplier_name)
                    params = (
                        name,
                        category,
                        brand,
                        int(supplier_id) if supplier_id else None,
                        int(stock),
                        float(unit_price),
                        float(purchase_price),
                        expiry_date,
                        bool(is_active),
                    )

                    if is_edit:
                        query = "UPDATE medicines SET MedicineName=%s, Category=%s, Brand=%s, SupplierID=%s, StockQty=%s, UnitPrice=%s, PurchasePrice=%s, ExpiryDate=%s, IsActive=%s WHERE MedicineID=%s"
                        params += (int(medicine_id),)
                    else:
                        query = "INSERT INTO medicines (MedicineName, Category, Brand, SupplierID, StockQty, UnitPrice, PurchasePrice, ExpiryDate, IsActive) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"

                    if execute_query(query, params):
                        st.success(
                            f"Medicine '{name}' was {'updated' if is_edit else 'added'} successfully!"
                        )
                        st.session_state.editing_medicine_id = None
                        st.rerun()

            if cancelled:
                st.session_state.editing_medicine_id = None
                st.rerun()

    def _handle_delete_confirmation(self, medicine_id):
        """Renders the confirmation dialog for a delete action."""
        if st.session_state.confirm_delete_medicine_id == medicine_id:
            st.warning(f"**Are you sure you want to delete this medicine?**")

            confirm_cols = st.columns([1, 1, 5])
            if confirm_cols[0].button(
                "Yes, Delete", key=f"confirm_del_med_{medicine_id}", type="primary"
            ):
                if execute_query(
                    "DELETE FROM medicines WHERE MedicineID=%s", (int(medicine_id),)
                ):
                    st.success("Medicine deleted successfully.")
                    st.session_state.confirm_delete_medicine_id = None
                    st.rerun()

            if confirm_cols[1].button(
                "No, Cancel", key=f"cancel_del_med_{medicine_id}"
            ):
                st.session_state.confirm_delete_medicine_id = None
                st.rerun()
