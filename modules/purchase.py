import streamlit as st
import pandas as pd
from datetime import date
import json
from db_connector import fetch_data, execute_query, execute_transaction


class PurchaseModule:
    """Manages Purchase Orders and Returns with full CRUD functionality."""

    def __init__(self):
        # Initialize session state for modals and forms
        if "show_create_po" not in st.session_state:
            st.session_state.show_create_po = False
        if "show_create_return" not in st.session_state:
            st.session_state.show_create_return = False
        if "editing_po_id" not in st.session_state:
            st.session_state.editing_po_id = None
        if "po_items" not in st.session_state:
            st.session_state.po_items = []

    def _get_data(self):
        """Fetches all necessary data from the database for this module."""
        self.purchase_orders = fetch_data(
            """
            SELECT p.*, s.SupplierName FROM purchase_orders p
            LEFT JOIN suppliers s ON p.SupplierID = s.SupplierID
            ORDER BY p.OrderDate DESC, p.PurchaseOrderID DESC
        """
        )
        self.suppliers = fetch_data(
            "SELECT SupplierID, SupplierName FROM suppliers WHERE IsActive = TRUE"
        )
        self.medicines = fetch_data(
            "SELECT MedicineID, MedicineName, PurchasePrice FROM medicines WHERE IsActive = TRUE"
        )
        self.purchase_returns = fetch_data(
            """
            SELECT pr.ReturnID, pr.ReturnDate, pr.Quantity, pr.Reason,
                   po.PurchaseOrderID, m.MedicineName, s.SupplierName
            FROM purchase_returns pr
            JOIN purchase_orders po ON pr.PurchaseOrderID = po.PurchaseOrderID
            JOIN medicines m ON pr.MedicineID = m.MedicineID
            JOIN suppliers s ON po.SupplierID = s.SupplierID
            ORDER BY pr.ReturnDate DESC
        """
        )

    def _display_purchase_orders(self):
        """Renders the UI for purchase order management, including search and actions."""
        st.subheader("Manage Purchase Orders")

        cols = st.columns([3, 1])
        with cols[0]:
            search_query = st.text_input("🔍 Search by PO ID, Supplier, or Status")
        with cols[1]:
            if st.button("📝 Create New Purchase Order", use_container_width=True):
                st.session_state.show_create_po = True
                st.session_state.editing_po_id = None
                st.session_state.po_items = []

        if search_query:
            po_df_search = self.purchase_orders.copy()
            po_df_search["PurchaseOrderID"] = po_df_search["PurchaseOrderID"].astype(
                str
            )
            filtered_pos = po_df_search[
                po_df_search["PurchaseOrderID"].str.contains(search_query, case=False)
                | po_df_search["SupplierName"].str.contains(search_query, case=False)
                | po_df_search["Status"].str.contains(search_query, case=False)
            ]
        else:
            filtered_pos = self.purchase_orders

        if filtered_pos.empty:
            st.info("No purchase orders found matching your search.")

        for _, row in filtered_pos.iterrows():
            with st.expander(
                f"PO #{row['PurchaseOrderID']} - {row['SupplierName']} (Status: {row['Status']})"
            ):
                cols = st.columns([2, 1])
                with cols[0]:
                    st.write(f"**Order Date:** {row['OrderDate']}")
                    st.write(f"**Expected Delivery:** {row['ExpectedDeliveryDate']}")
                with cols[1]:
                    action_cols = st.columns(3)
                    if row["Status"] == "Pending":
                        if action_cols[0].button(
                            "✏️ Edit",
                            key=f"edit_{row['PurchaseOrderID']}",
                            use_container_width=True,
                        ):
                            st.session_state.editing_po_id = row["PurchaseOrderID"]
                            st.session_state.show_create_po = False
                            st.rerun()
                        if action_cols[1].button(
                            "🗑️ Delete",
                            key=f"del_{row['PurchaseOrderID']}",
                            use_container_width=True,
                        ):
                            self._handle_po_delete(row["PurchaseOrderID"])
                    if row["Status"] == "Pending":
                        if action_cols[2].button(
                            "✅ Mark Received",
                            key=f"receive_{row['PurchaseOrderID']}",
                            use_container_width=True,
                        ):
                            self._mark_po_as_received(
                                row["PurchaseOrderID"], row["ItemsData"]
                            )

                items_data = row["ItemsData"]
                if items_data and isinstance(items_data, str):
                    items = pd.DataFrame(json.loads(items_data))
                else:
                    items = pd.DataFrame(items_data if items_data else [])
                st.dataframe(items, use_container_width=True)

    def _create_po_modal(self):
        """Renders a UI for creating a new PO, correctly separating item adding from form submission."""
        st.title("Create New Purchase Order")
        st.subheader("1. Add Items to Order")
        cols = st.columns([2, 1, 1])
        med_name = cols[0].selectbox(
            "Select Medicine", self.medicines["MedicineName"], key="med_select"
        )
        qty = cols[1].number_input("Quantity", min_value=1, step=1)

        if cols[2].button("Add Item", use_container_width=True):
            med_id = self.medicines[self.medicines["MedicineName"] == med_name][
                "MedicineID"
            ].iloc[0]
            price = self.medicines[self.medicines["MedicineName"] == med_name][
                "PurchasePrice"
            ].iloc[0]
            st.session_state.po_items.append(
                {
                    "MedicineID": int(med_id),
                    "MedicineName": med_name,
                    "Quantity": int(qty),
                    "PurchasePrice": float(price),
                }
            )

        if st.session_state.po_items:
            st.write("Order Items:")
            st.dataframe(
                pd.DataFrame(st.session_state.po_items), use_container_width=True
            )
            if st.button("Clear All Items", type="secondary"):
                st.session_state.po_items = []
                st.rerun()
        st.markdown("---")

        with st.form("create_po_form"):
            st.subheader("2. Finalize and Submit Order")
            supplier_name = st.selectbox(
                "Select Supplier", self.suppliers["SupplierName"]
            )
            order_date = st.date_input("Order Date", value=date.today())
            expected_date = st.date_input("Expected Delivery Date", value=date.today())

            submit_cols = st.columns([1, 1, 2])
            submitted = submit_cols[0].form_submit_button(
                "Create Purchase Order", use_container_width=True
            )
            cancelled = submit_cols[1].form_submit_button(
                "Cancel", type="secondary", use_container_width=True
            )

            if submitted:
                if not supplier_name or not st.session_state.po_items:
                    st.error("Please select a supplier and add at least one item.")
                else:
                    supplier_id = self.suppliers[
                        self.suppliers["SupplierName"] == supplier_name
                    ]["SupplierID"].iloc[0]
                    if execute_query(
                        "INSERT INTO purchase_orders (SupplierID, OrderDate, ExpectedDeliveryDate, Status, ItemsData) VALUES (%s, %s, %s, 'Pending', %s)",
                        (
                            int(supplier_id),
                            order_date,
                            expected_date,
                            st.session_state.po_items,
                        ),
                    ):
                        st.success("Purchase Order created successfully!")
                        st.session_state.show_create_po = False
                        st.session_state.po_items = []
                        st.rerun()

            if cancelled:
                st.session_state.show_create_po = False
                st.session_state.po_items = []
                st.rerun()

    def _handle_po_delete(self, po_id):
        """Deletes a purchase order after confirmation."""
        st.warning(f"Are you sure you want to delete Purchase Order #{po_id}?")
        if st.button("Confirm Delete", key=f"confirm_del_{po_id}"):
            if execute_query(
                "DELETE FROM purchase_orders WHERE PurchaseOrderID = %s", (po_id,)
            ):
                st.success(f"Purchase Order #{po_id} has been deleted.")
                st.rerun()
            else:
                st.error("Failed to delete the purchase order.")

    def _edit_po_modal(self):
        """Renders a modal form to edit an existing Purchase Order."""
        po_to_edit = self.purchase_orders[
            self.purchase_orders["PurchaseOrderID"] == st.session_state.editing_po_id
        ].iloc[0]
        if "po_items" not in st.session_state or not st.session_state.po_items:
            st.session_state.po_items = (
                json.loads(po_to_edit["ItemsData"])
                if po_to_edit["ItemsData"] and isinstance(po_to_edit["ItemsData"], str)
                else []
            )
        with st.form("edit_po_form"):
            st.title(f"✏️ Editing Purchase Order #{st.session_state.editing_po_id}")
            supplier_names = self.suppliers["SupplierName"].tolist()
            current_supplier_index = (
                supplier_names.index(po_to_edit["SupplierName"])
                if po_to_edit["SupplierName"] in supplier_names
                else 0
            )
            supplier_name = st.selectbox(
                "Select Supplier", supplier_names, index=current_supplier_index
            )
            order_date = st.date_input(
                "Order Date", value=pd.to_datetime(po_to_edit["OrderDate"])
            )
            expected_date = st.date_input(
                "Expected Delivery Date",
                value=pd.to_datetime(po_to_edit["ExpectedDeliveryDate"]),
            )
            st.subheader("Edit Items in Order")
            st.session_state.po_items = st.data_editor(
                pd.DataFrame(st.session_state.po_items),
                num_rows="dynamic",
                use_container_width=True,
            )
            submit_cols = st.columns([1, 1, 2])
            if submit_cols[0].form_submit_button(
                "Update Purchase Order", use_container_width=True
            ):
                if not supplier_name or st.session_state.po_items.empty:
                    st.error("Supplier and at least one item are required.")
                else:
                    supplier_id = self.suppliers[
                        self.suppliers["SupplierName"] == supplier_name
                    ]["SupplierID"].iloc[0]
                    items_data = st.session_state.po_items.to_dict("records")
                    if execute_query(
                        "UPDATE purchase_orders SET SupplierID=%s, OrderDate=%s, ExpectedDeliveryDate=%s, ItemsData=%s WHERE PurchaseOrderID=%s",
                        (
                            int(supplier_id),
                            order_date,
                            expected_date,
                            items_data,
                            st.session_state.editing_po_id,
                        ),
                    ):
                        st.success("Purchase Order updated successfully!")
                        st.session_state.editing_po_id = None
                        st.session_state.po_items = []
                        st.rerun()
            if submit_cols[1].form_submit_button(
                "Cancel", type="secondary", use_container_width=True
            ):
                st.session_state.editing_po_id = None
                st.session_state.po_items = []
                st.rerun()

    def _mark_po_as_received(self, po_id, items_data_json):
        """Updates PO status and medicine stock in a single transaction."""
        st.info("Processing order... Please wait.")
        items_df = pd.DataFrame(
            json.loads(items_data_json)
            if items_data_json and isinstance(items_data_json, str)
            else []
        )
        queries = [
            (
                "UPDATE purchase_orders SET Status = 'Received' WHERE PurchaseOrderID = %s",
                (po_id,),
            )
        ]
        for _, item in items_df.iterrows():
            queries.append(
                (
                    "UPDATE medicines SET StockQty = StockQty + %s WHERE MedicineID = %s",
                    (item["Quantity"], item["MedicineID"]),
                )
            )
        if execute_transaction(queries):
            st.success(f"PO #{po_id} marked as received and stock updated!")
            st.rerun()
        else:
            st.error("An error occurred. Stock levels have not been changed.")

    def _display_purchase_returns(self):
        """Renders the UI for managing purchase returns."""
        st.subheader("Manage Purchase Returns")
        if st.button("↩️ Create New Return"):
            st.session_state.show_create_return = True
        if st.session_state.show_create_return:
            self._create_return_form()
        st.markdown("---")
        st.subheader("Return History")
        if self.purchase_returns.empty:
            st.info("No purchase returns have been recorded yet.")
        else:
            st.dataframe(
                self.purchase_returns, use_container_width=True, hide_index=True
            )

    def _create_return_form(self):
        """Renders a form to create a new purchase return."""
        with st.form("create_return_form"):
            st.subheader("New Purchase Return Form")
            received_pos = self.purchase_orders[
                self.purchase_orders["Status"] == "Received"
            ]
            if received_pos.empty:
                st.warning(
                    "No 'Received' purchase orders available to create a return."
                )
                st.form_submit_button(
                    "Close",
                    on_click=lambda: st.session_state.update(show_create_return=False),
                )
                return

            po_options = {
                f"PO #{row['PurchaseOrderID']} - {row['SupplierName']}": row
                for _, row in received_pos.iterrows()
            }
            selected_po_str = st.selectbox(
                "Select a Purchase Order to Return From", po_options.keys()
            )

            selected_po_data = po_options[selected_po_str]
            po_items = json.loads(selected_po_data["ItemsData"])

            # --- ✅ FIX STARTS HERE ---
            # Create a mapping from MedicineID to MedicineName for quick lookups
            medicine_id_to_name = pd.Series(
                self.medicines.MedicineName.values, index=self.medicines.MedicineID
            ).to_dict()
            # Add the MedicineName to each item in the list using the mapping
            for item in po_items:
                item["MedicineName"] = medicine_id_to_name.get(
                    item["MedicineID"], "Unknown Medicine"
                )
            # --- ✅ FIX ENDS HERE ---

            medicine_options = {item["MedicineName"]: item for item in po_items}
            selected_med_name = st.selectbox(
                "Select Medicine to Return", medicine_options.keys()
            )

            selected_item_data = medicine_options[selected_med_name]
            max_qty = selected_item_data["Quantity"]
            return_qty = st.number_input(
                f"Quantity to Return (Max: {max_qty})",
                min_value=1,
                max_value=max_qty,
                step=1,
            )
            return_date = st.date_input("Return Date", value=date.today())
            reason = st.text_area("Reason for Return")

            submit_cols = st.columns([1, 1, 2])
            if submit_cols[0].form_submit_button(
                "Submit Return", use_container_width=True
            ):
                if not reason:
                    st.error("A reason for the return is required.")
                else:
                    medicine_id = selected_item_data["MedicineID"]
                    po_id = selected_po_data["PurchaseOrderID"]
                    queries = [
                        (
                            "INSERT INTO purchase_returns (PurchaseOrderID, MedicineID, Quantity, ReturnDate, Reason) VALUES (%s, %s, %s, %s, %s)",
                            (po_id, medicine_id, return_qty, return_date, reason),
                        ),
                        (
                            "UPDATE medicines SET StockQty = StockQty - %s WHERE MedicineID = %s",
                            (return_qty, medicine_id),
                        ),
                    ]
                    if execute_transaction(queries):
                        st.success(
                            "Purchase return recorded successfully and stock updated!"
                        )
                        st.session_state.show_create_return = False
                        st.rerun()
                    else:
                        st.error("Failed to process the return.")
            if submit_cols[1].form_submit_button(
                "Cancel", type="secondary", use_container_width=True
            ):
                st.session_state.show_create_return = False
                st.rerun()

    def render(self):
        """Main render method for the purchase module."""
        st.title("🛒 Purchase Management")
        self._get_data()

        if st.session_state.editing_po_id:
            self._edit_po_modal()
        elif st.session_state.show_create_po:
            self._create_po_modal()
        else:
            tab1, tab2 = st.tabs(["Purchase Orders", "Purchase Returns"])
            with tab1:
                self._display_purchase_orders()
            with tab2:
                self._display_purchase_returns()
