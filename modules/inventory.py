import streamlit as st
import pandas as pd
from datetime import date, timedelta
from db_connector import fetch_data, execute_query


class InventoryModule:
    """
    Manages all inventory stock levels with a premium UI, stock adjustments, KPIs,
    alerts, and advanced filtering capabilities. This module is read-only for
    medicine details but allows full control over stock quantities.
    """

    def __init__(self):
        """Initializes session state keys for the module."""
        st.session_state.setdefault("adjusting_stock_item_id", None)
        st.session_state.setdefault("viewing_inventory_kpi", None)

    def _get_data(self):
        """
        Fetches all necessary data from the database, calculates KPIs, and
        computes the total stock value.
        """
        self.inventory = fetch_data(
            "SELECT m.*, s.SupplierName FROM medicines m LEFT JOIN suppliers s ON m.SupplierID = s.SupplierID ORDER BY m.MedicineName"
        )

        if self.inventory is not None and not self.inventory.empty:
            self.inventory["ExpiryDate"] = pd.to_datetime(self.inventory["ExpiryDate"])

            # --- Main KPIs ---
            self.kpi_total_items = len(self.inventory)
            self.low_stock_df = self.inventory[self.inventory["StockQty"] < 10]
            self.kpi_low_stock_count = len(self.low_stock_df)
            self.out_of_stock_df = self.inventory[self.inventory["StockQty"] == 0]
            self.kpi_out_of_stock_count = len(self.out_of_stock_df)

            expiring_soon_date = pd.to_datetime(date.today() + timedelta(days=30))
            self.expiring_soon_df = self.inventory[
                (self.inventory["ExpiryDate"] <= expiring_soon_date)
                & (self.inventory["ExpiryDate"] >= pd.to_datetime(date.today()))
            ]
            self.kpi_expiring_soon_count = len(self.expiring_soon_df)

            # --- Value KPI ---
            self.inventory["StockValue"] = (
                self.inventory["StockQty"] * self.inventory["PurchasePrice"]
            )
            self.kpi_total_stock_value = self.inventory["StockValue"].sum()
        else:
            self.kpi_total_items = self.kpi_low_stock_count = (
                self.kpi_expiring_soon_count
            ) = self.kpi_out_of_stock_count = self.kpi_total_stock_value = 0
            self.low_stock_df = self.expiring_soon_df = self.out_of_stock_df = (
                pd.DataFrame()
            )

    def render(self):
        """Main render method that routes to the correct view (list or form)."""
        self._get_data()
        st.title("📦 Inventory Stock Management")

        if st.session_state.adjusting_stock_item_id is not None:
            self._render_stock_adjustment_form(st.session_state.adjusting_stock_item_id)
        else:
            self._render_main_view()

    def _render_main_view(self):
        """Renders KPIs, analytics, and the main inventory view with a search sidebar."""
        # --- KPIs ---
        kpi_cols = st.columns(5)
        kpi_cols[0].markdown(
            f'<div class.kpi-card"><p class="kpi-title">Total Unique Items</p><p class="kpi-value">{self.kpi_total_items}</p></div>',
            unsafe_allow_html=True,
        )
        with kpi_cols[1]:
            if st.button(
                "Low Stock (<10)", key="low_stock_kpi", use_container_width=True
            ):
                st.session_state.viewing_inventory_kpi = "low_stock"
                st.rerun()
            st.markdown(
                f'<div class="kpi-card" style="margin-top:-50px;"><p class="kpi-title">Low Stock</p><p class="kpi-value">{self.kpi_low_stock_count}</p></div>',
                unsafe_allow_html=True,
            )
        with kpi_cols[2]:
            if st.button(
                "Expiring Soon (30d)", key="exp_soon_kpi", use_container_width=True
            ):
                st.session_state.viewing_inventory_kpi = "expiring_soon"
                st.rerun()
            st.markdown(
                f'<div class="kpi-card" style="margin-top:-50px;"><p class="kpi-title">Expiring Soon</p><p class="kpi-value">{self.kpi_expiring_soon_count}</p></div>',
                unsafe_allow_html=True,
            )
        with kpi_cols[3]:
            if st.button(
                "Out of Stock", key="out_of_stock_kpi", use_container_width=True
            ):
                st.session_state.viewing_inventory_kpi = "out_of_stock"
                st.rerun()
            st.markdown(
                f'<div class="kpi-card" style="margin-top:-50px;"><p class="kpi-title">Out of Stock</p><p class="kpi-value">{self.kpi_out_of_stock_count}</p></div>',
                unsafe_allow_html=True,
            )
        kpi_cols[4].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Total Stock Value</p><p class="kpi-value">Rs {self.kpi_total_stock_value:,.0f}</p></div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        if st.session_state.viewing_inventory_kpi:
            self._display_kpi_drilldown()
        else:
            self._display_filtered_inventory()
            self._display_analytics()

    def _display_kpi_drilldown(self):
        """Displays the filtered list when a KPI is clicked."""
        kpi_map = {
            "low_stock": (self.low_stock_df, "Items with Low Stock"),
            "expiring_soon": (self.expiring_soon_df, "Items Expiring Soon"),
            "out_of_stock": (self.out_of_stock_df, "Out of Stock Items"),
        }
        df, title = kpi_map.get(
            st.session_state.viewing_inventory_kpi, (pd.DataFrame(), "Inventory")
        )

        st.subheader(title)
        if st.button("⬅️ Back to Full Inventory"):
            st.session_state.viewing_inventory_kpi = None
            st.rerun()
        st.dataframe(df, use_container_width=True, hide_index=True)

    def _display_filtered_inventory(self):
        """Displays advanced search filters and the resulting inventory list."""
        st.sidebar.header("🔍 Search & Filter Inventory")

        search_term = st.sidebar.text_input("Search by Item Name")

        categories = ["All"] + sorted(
            self.inventory["Category"].dropna().unique().tolist()
        )
        selected_category = st.sidebar.selectbox("Filter by Category", categories)

        suppliers = ["All"] + sorted(
            self.inventory["SupplierName"].dropna().unique().tolist()
        )
        selected_supplier = st.sidebar.selectbox("Filter by Supplier", suppliers)

        stock_levels = ["All", "Low Stock", "Out of Stock"]
        selected_stock = st.sidebar.selectbox("Filter by Stock Level", stock_levels)

        expiry_status = ["All", "Expiring Soon", "Expired"]
        selected_expiry = st.sidebar.selectbox("Filter by Expiry Status", expiry_status)

        # --- Filtering Logic ---
        filtered_df = self.inventory.copy()
        if search_term:
            filtered_df = filtered_df[
                filtered_df["MedicineName"].str.contains(
                    search_term, case=False, na=False
                )
            ]
        if selected_category != "All":
            filtered_df = filtered_df[filtered_df["Category"] == selected_category]
        if selected_supplier != "All":
            filtered_df = filtered_df[filtered_df["SupplierName"] == selected_supplier]
        if selected_stock == "Low Stock":
            filtered_df = filtered_df[filtered_df["StockQty"] < 10]
        elif selected_stock == "Out of Stock":
            filtered_df = filtered_df[filtered_df["StockQty"] == 0]
        if selected_expiry == "Expiring Soon":
            exp_soon_date = pd.to_datetime(date.today() + timedelta(days=30))
            filtered_df = filtered_df[
                (filtered_df["ExpiryDate"] <= exp_soon_date)
                & (filtered_df["ExpiryDate"] >= pd.to_datetime(date.today()))
            ]
        elif selected_expiry == "Expired":
            filtered_df = filtered_df[
                filtered_df["ExpiryDate"] < pd.to_datetime(date.today())
            ]

        st.subheader("Inventory Details")
        if not filtered_df.empty:
            st.download_button(
                label="📥 Export as CSV",
                data=filtered_df.to_csv(index=False).encode("utf-8"),
                file_name="inventory_report.csv",
                mime="text/csv",
            )
            for _, item in filtered_df.iterrows():
                self._render_inventory_row(item)
        else:
            st.warning("No items match your search criteria.")

    def _render_inventory_row(self, item):
        """Renders a single inventory item's row with alerts and actions."""
        st.markdown("---")

        # --- Alerts ---
        alerts = []
        if item["StockQty"] < 10 and item["StockQty"] > 0:
            alerts.append("⚠️ Low Stock")
        days_left = (item["ExpiryDate"].date() - date.today()).days
        if 0 <= days_left <= 30:
            alerts.append("⏳ Expiring Soon")

        row_cols = st.columns([3, 2, 2, 2, 2])

        name_display = f"**{item['MedicineName']}**"
        if alerts:
            name_display += (
                f"  <small style='color:orange;'>{' | '.join(alerts)}</small>"
            )
        row_cols[0].markdown(name_display, unsafe_allow_html=True)
        row_cols[0].caption(
            f"{item.get('Category', 'N/A')} | {item.get('Brand', 'N/A')}"
        )

        stock_qty = item["StockQty"]
        stock_class = (
            "status-ok"
            if stock_qty >= 10
            else ("status-expiring" if 0 < stock_qty < 10 else "status-low")
        )
        row_cols[1].markdown(
            f"Stock: <span class='status-tag {stock_class}'>{stock_qty}</span>",
            unsafe_allow_html=True,
        )

        exp_date = item["ExpiryDate"].date()
        exp_class = (
            "status-ok"
            if days_left > 30
            else ("status-expiring" if 0 <= days_left <= 30 else "status-low")
        )
        row_cols[2].markdown(
            f"Expiry: <span class='status-tag {exp_class}'>{exp_date.strftime('%b %d, %Y')}</span>",
            unsafe_allow_html=True,
        )

        row_cols[3].markdown(
            f"**Supplier**<br>{item.get('SupplierName', 'N/A')}", unsafe_allow_html=True
        )

        with row_cols[4]:
            if st.button(
                "⚙️ Adjust Stock",
                key=f"adjust_inv_{item['MedicineID']}",
                use_container_width=True,
            ):
                st.session_state.adjusting_stock_item_id = item["MedicineID"]
                st.rerun()

    def _render_stock_adjustment_form(self, item_id):
        """Renders the form for adjusting the stock of a single item."""
        item_data = self.inventory[self.inventory["MedicineID"] == item_id].iloc[0]

        with st.form(key="stock_adjustment_form"):
            st.subheader(f"Adjust Stock for: {item_data['MedicineName']}")

            st.metric("Current Stock", int(item_data["StockQty"]))

            adj_type = st.selectbox(
                "Adjustment Type",
                ["Add to Stock", "Remove from Stock", "Set to New Value (Correction)"],
            )
            quantity = st.number_input("Quantity", min_value=1, step=1)
            notes = st.text_area(
                "Reason / Notes (e.g., 'Received shipment', 'Expired stock disposal')"
            )

            submitted = st.form_submit_button("Save Adjustment", type="primary")
            cancelled = st.form_submit_button("Cancel")

            if submitted:
                current_stock = int(item_data["StockQty"])
                new_stock = current_stock

                if adj_type == "Add to Stock":
                    new_stock = current_stock + quantity
                elif adj_type == "Remove from Stock":
                    new_stock = current_stock - quantity
                elif adj_type == "Set to New Value (Correction)":
                    new_stock = quantity

                if new_stock < 0:
                    st.error("Stock quantity cannot be negative.")
                else:
                    query = "UPDATE medicines SET StockQty = %s WHERE MedicineID = %s"
                    if execute_query(query, (int(new_stock), int(item_id))):
                        st.success(
                            f"Stock for '{item_data['MedicineName']}' updated to {new_stock}."
                        )
                        st.session_state.adjusting_stock_item_id = None
                        st.rerun()
            if cancelled:
                st.session_state.adjusting_stock_item_id = None
                st.rerun()

    def _display_analytics(self):
        """Displays charts for stock value analytics."""
        st.markdown("---")
        st.subheader("📊 Inventory Analytics")

        if not self.inventory.empty:
            col1, col2 = st.columns(2)

            # Stock Value by Supplier
            supplier_value = (
                self.inventory.groupby("SupplierName")["StockValue"]
                .sum()
                .sort_values(ascending=False)
            )
            fig1 = pd.DataFrame(
                {"Supplier": supplier_value.index, "Total Value": supplier_value.values}
            )
            with col1:
                st.write("**Stock Value by Supplier**")
                st.bar_chart(fig1, x="Supplier", y="Total Value")

            # Stock Value by Category
            category_value = (
                self.inventory.groupby("Category")["StockValue"]
                .sum()
                .sort_values(ascending=False)
            )
            fig2 = pd.DataFrame(
                {"Category": category_value.index, "Total Value": category_value.values}
            )
            with col2:
                st.write("**Stock Value by Category**")
                st.bar_chart(fig2, x="Category", y="Total Value")
        else:
            st.info("No inventory data available for analytics.")
