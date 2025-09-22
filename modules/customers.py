import streamlit as st
import pandas as pd
from datetime import date
from db_connector import fetch_data, execute_query


class CustomersModule:
    """
    Manages all customer-related operations with a premium UI, including full CRUD,
    real-time KPIs, advanced filtering, pagination, and loyalty point management.
    """

    def __init__(self):
        """Initializes session state keys for handling UI interactions and state."""
        st.session_state.setdefault("editing_customer_id", None)
        st.session_state.setdefault("confirm_delete_customer_id", None)
        st.session_state.setdefault("customer_page_number", 1)

    def _calculate_age(self, born):
        """Calculates age in years from a date of birth."""
        if pd.isnull(born) or not isinstance(born, date):
            return None
        today = date.today()
        return (
            today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        )

    def _get_data(self):
        """
        Fetches customer data, calculates the 'age' column, and computes all KPIs.
        """
        self.customers = fetch_data("SELECT * FROM customers")

        if self.customers is not None and not self.customers.empty:
            # --- Data Type Conversion and Calculated Columns ---
            date_cols = ["dob", "last_purchase_date", "created_at", "updated_at"]
            for col in date_cols:
                self.customers[col] = pd.to_datetime(
                    self.customers[col], errors="coerce"
                ).dt.date

            self.customers["age"] = self.customers["dob"].apply(self._calculate_age)

            # --- KPI Calculations ---
            self.kpi_total_customers = len(self.customers)
            self.kpi_active_customers = self.customers[
                self.customers["status"] == "Active"
            ].shape[0]
            self.kpi_inactive_customers = (
                self.kpi_total_customers - self.kpi_active_customers
            )
            self.kpi_avg_age = (
                int(self.customers["age"].mean())
                if not self.customers["age"].isnull().all()
                else 0
            )
            self.kpi_outstanding_customers = self.customers[
                self.customers["outstanding_amount"] > 0
            ].shape[0]
            self.top_5_customers = self.customers.nlargest(5, "total_purchases")[
                ["name", "total_purchases"]
            ]
        else:
            self.kpi_total_customers = self.kpi_active_customers = (
                self.kpi_inactive_customers
            ) = 0
            self.kpi_avg_age = self.kpi_outstanding_customers = 0
            self.top_5_customers = pd.DataFrame(columns=["name", "total_purchases"])

    def render(self):
        """Main render method that routes to the correct view (list or form)."""
        self._get_data()
        st.title("👥 Advanced Customer Management")

        if st.session_state.editing_customer_id is not None:
            self._render_customer_form(st.session_state.editing_customer_id)
        else:
            self._render_main_view()

    def _render_main_view(self):
        """Renders KPIs and the main customer view with filters and pagination."""
        self._render_kpis()
        st.markdown("---")
        self._display_filtered_customers()

    def _render_kpis(self):
        """Renders the KPI cards at the top of the page."""
        kpi_cols = st.columns(5)
        kpi_cols[0].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Total Customers</p><p class="kpi-value">{self.kpi_total_customers}</p></div>',
            unsafe_allow_html=True,
        )
        kpi_cols[1].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Active / Inactive</p><p class="kpi-value">{self.kpi_active_customers} / {self.kpi_inactive_customers}</p></div>',
            unsafe_allow_html=True,
        )
        kpi_cols[2].markdown(
            f'<div class="kpi-card"><p class="kpi-title">Average Age</p><p class="kpi-value">{self.kpi_avg_age}</p></div>',
            unsafe_allow_html=True,
        )
        kpi_cols[3].markdown(
            f'<div class="kpi-card"><p class="kpi-title">With Dues</p><p class="kpi-value">{self.kpi_outstanding_customers}</p></div>',
            unsafe_allow_html=True,
        )
        with kpi_cols[4]:
            st.markdown(
                '<div class="kpi-card" style="text-align:left; padding-left:25px;"><p class="kpi-title">Top 5 by Purchases</p></div>',
                unsafe_allow_html=True,
            )
            for i, row in self.top_5_customers.iterrows():
                st.markdown(
                    f"**{row['name']}**: Rs {row['total_purchases']:,.0f}",
                    help=f"Exact: {row['total_purchases']}",
                )

    def _display_filtered_customers(self):
        """Displays advanced search filters and the resulting paginated customer list."""
        st.sidebar.header("🔍 Search & Filter Customers")
        search_term = st.sidebar.text_input("Search by Name, Phone, Email, City...")
        status_filter = st.sidebar.selectbox(
            "Filter by Status", ["All", "Active", "Inactive"]
        )
        gender_filter = st.sidebar.selectbox(
            "Filter by Gender", ["All", "Male", "Female", "Other"]
        )

        # --- Filtering Logic ---
        filtered_df = self.customers.copy()
        if search_term:
            filtered_df = filtered_df[
                filtered_df.apply(
                    lambda row: any(
                        search_term.lower() in str(val).lower()
                        for val in row[["name", "phone", "email", "city", "country"]]
                    ),
                    axis=1,
                )
            ]
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["status"] == status_filter]
        if gender_filter != "All":
            filtered_df = filtered_df[filtered_df["gender"] == gender_filter]

        # --- Display and Pagination ---
        list_col, btn_col = st.columns([3, 1])
        list_col.subheader("All Customers")
        if btn_col.button("➕ Add New Customer", use_container_width=True):
            st.session_state.editing_customer_id = "new"
            st.rerun()

        if not filtered_df.empty:
            st.download_button(
                "📥 Export as CSV",
                filtered_df.to_csv(index=False).encode("utf-8"),
                "customers.csv",
                "text/csv",
            )

            items_per_page = 10
            total_pages = (len(filtered_df) + items_per_page - 1) // items_per_page
            page_number = st.number_input(
                "Page",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.customer_page_number,
                key="cust_page_selector",
            )
            st.session_state.customer_page_number = page_number

            start_idx = (page_number - 1) * items_per_page
            end_idx = start_idx + items_per_page
            paginated_df = filtered_df.iloc[start_idx:end_idx]

            for _, customer in paginated_df.iterrows():
                self._render_customer_row(customer)
        else:
            st.warning("No customers match your search criteria.")

    def _render_customer_row(self, customer):
        """Renders a single customer's information in a detailed row format."""
        st.markdown("---")
        row_cols = st.columns((3, 3, 2, 2, 2))

        status_class = "status-ok" if customer["status"] == "Active" else "status-low"
        row_cols[0].markdown(
            f"**{customer['name']}** ({customer.get('age', 'N/A')} yrs, {customer.get('gender', 'N/A')})"
        )
        row_cols[0].caption(
            f"📍 {customer.get('city', 'N/A')}, {customer.get('country', 'N/A')}"
        )

        row_cols[1].markdown(
            f"📞 {customer.get('phone', 'N/A')}<br>✉️ {customer.get('email', 'N/A')}",
            unsafe_allow_html=True,
        )

        row_cols[2].markdown(
            f"**Status:**<br><span class='status-tag {status_class}'>{customer['status']}</span>",
            unsafe_allow_html=True,
        )

        row_cols[3].markdown(
            f"**Purchases:**<br>Rs {customer.get('total_purchases', 0):,.0f}",
            unsafe_allow_html=True,
        )
        row_cols[3].markdown(
            f"**Dues:**<br>Rs {customer.get('outstanding_amount', 0):,.0f}",
            unsafe_allow_html=True,
        )

        with row_cols[4]:
            st.write("")  # For vertical alignment
            action_cols = st.columns(2)
            if action_cols[0].button(
                "✏️", key=f"edit_cust_{customer['id']}", help="Edit Customer"
            ):
                st.session_state.editing_customer_id = customer["id"]
                st.rerun()
            if action_cols[1].button(
                "🗑️",
                key=f"del_cust_{customer['id']}",
                help="Delete Customer (Set Inactive)",
            ):
                st.session_state.confirm_delete_customer_id = customer["id"]
                st.rerun()

        self._handle_delete_confirmation(customer["id"])

    def _render_customer_form(self, customer_id):
        """Renders the comprehensive form for adding or editing a customer."""
        is_edit = customer_id != "new"
        title = "Edit Customer Details" if is_edit else "➕ Add New Customer"
        customer_data = (
            self.customers[self.customers["id"] == customer_id].iloc[0].to_dict()
            if is_edit
            else {}
        )

        with st.form("customer_form"):
            st.subheader(title)

            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Full Name*", value=customer_data.get("name", ""))
            dob = c2.date_input(
                "Date of Birth",
                value=customer_data.get("dob"),
                min_value=date(1920, 1, 1),
                max_value=date.today(),
            )
            age_display = self._calculate_age(dob)
            c3.metric(
                "Age", f"{age_display} years" if age_display is not None else "N/A"
            )

            c1, c2 = st.columns(2)
            phone = c1.text_input("Phone*", value=customer_data.get("phone", ""))
            email = c2.text_input("Email", value=customer_data.get("email", ""))
            gender = c1.selectbox(
                "Gender",
                ["Male", "Female", "Other"],
                index=["Male", "Female", "Other"].index(
                    customer_data.get("gender", "Male")
                ),
            )
            status = c2.selectbox(
                "Status",
                ["Active", "Inactive"],
                index=["Active", "Inactive"].index(
                    customer_data.get("status", "Active")
                ),
            )

            st.markdown("<h6>Address Details</h6>", unsafe_allow_html=True)
            address = st.text_input(
                "Street Address", value=customer_data.get("address", "")
            )
            c1, c2, c3, c4 = st.columns(4)
            city = c1.text_input("City", value=customer_data.get("city", ""))
            state = c2.text_input(
                "State/Province", value=customer_data.get("state", "")
            )
            postal_code = c3.text_input(
                "Postal Code", value=customer_data.get("postal_code", "")
            )
            country = c4.text_input("Country", value=customer_data.get("country", ""))

            st.markdown("<h6>Financial & Loyalty Details</h6>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            total_purchases = c1.number_input(
                "Total Purchases",
                value=float(customer_data.get("total_purchases", 0.0)),
                format="%.2f",
            )
            outstanding_amount = c2.number_input(
                "Outstanding Amount",
                value=float(customer_data.get("outstanding_amount", 0.0)),
                format="%.2f",
            )
            last_purchase_date = c3.date_input(
                "Last Purchase Date", value=customer_data.get("last_purchase_date")
            )
            loyalty_points = c4.number_input(
                "Loyalty Points",
                value=int(customer_data.get("loyalty_points", 0)),
                step=1,
            )
            notes = st.text_area("Notes", value=customer_data.get("notes", ""))

            submitted = st.form_submit_button("Save Customer", type="primary")
            cancelled = st.form_submit_button("Cancel")

            if submitted:
                if not name:
                    st.error("Customer Name is a required field.")
                # Add more validation as needed (e.g., phone format)
                else:
                    params = (
                        name,
                        gender,
                        dob,
                        phone,
                        email,
                        address,
                        city,
                        state,
                        postal_code,
                        country,
                        status,
                        total_purchases,
                        outstanding_amount,
                        last_purchase_date,
                        loyalty_points,
                        notes,
                    )
                    if is_edit:
                        query = "UPDATE customers SET name=%s, gender=%s, dob=%s, phone=%s, email=%s, address=%s, city=%s, state=%s, postal_code=%s, country=%s, status=%s, total_purchases=%s, outstanding_amount=%s, last_purchase_date=%s, loyalty_points=%s, notes=%s, updated_at=NOW() WHERE id=%s"
                        params += (int(customer_id),)
                    else:
                        query = "INSERT INTO customers (name, gender, dob, phone, email, address, city, state, postal_code, country, status, total_purchases, outstanding_amount, last_purchase_date, loyalty_points, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

                    if execute_query(query, params):
                        st.success(f"Customer '{name}' was saved successfully!")
                        st.session_state.editing_customer_id = None
                        st.rerun()
            if cancelled:
                st.session_state.editing_customer_id = None
                st.rerun()

    def _handle_delete_confirmation(self, customer_id):
        """Renders the confirmation dialog for a soft delete (setting status to Inactive)."""
        if st.session_state.confirm_delete_customer_id == customer_id:
            st.warning(
                f"**Are you sure you want to set this customer to Inactive?** This is a soft delete."
            )
            confirm_cols = st.columns([1, 1, 4])
            if confirm_cols[0].button(
                "Yes, Set Inactive",
                key=f"confirm_del_cust_{customer_id}",
                type="primary",
            ):
                if execute_query(
                    "UPDATE customers SET status = 'Inactive' WHERE id=%s",
                    (int(customer_id),),
                ):
                    st.success("Customer status set to Inactive.")
                    st.session_state.confirm_delete_customer_id = None
                    st.rerun()
            if confirm_cols[1].button(
                "No, Cancel", key=f"cancel_del_cust_{customer_id}"
            ):
                st.session_state.confirm_delete_customer_id = None
                st.rerun()
