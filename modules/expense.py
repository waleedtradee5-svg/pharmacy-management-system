import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
from db_connector import fetch_data, execute_query
import json
import os

# --- Constants for File Uploads ---
ATTACHMENT_DIR = "attachments"
if not os.path.exists(ATTACHMENT_DIR):
    os.makedirs(ATTACHMENT_DIR)


class ExpensesModule:
    """
    Manages all aspects of expense tracking including CRUD, approvals, attachments,
    analytics, and role-based access control.
    """

    def __init__(self):
        """Initializes session state keys for managing the UI."""
        st.session_state.setdefault("editing_expense_id", None)
        st.session_state.setdefault("expense_user_role", "Admin")  # For demo purposes
        st.session_state.setdefault(
            "expense_filters",
            {
                "date_range": (date.today() - timedelta(days=30), date.today()),
                "category": "All",
                "status": "All",
                "search_term": "",
            },
        )

    def _get_filtered_data(self):
        """
        Fetches and filters expense data from the database based on sidebar filters.
        This method uses dynamic SQL for efficient querying.
        """
        filters = st.session_state.expense_filters
        query = "SELECT * FROM expenses WHERE 1=1"
        params = []

        # Date Range Filter
        start_date, end_date = filters["date_range"]
        query += " AND ExpenseDate BETWEEN %s AND %s"
        params.extend([start_date, end_date])

        # Category Filter
        if filters["category"] != "All":
            query += " AND Category = %s"
            params.append(filters["category"])

        # Approval Status Filter
        if filters["status"] != "All":
            query += " AND ApprovalStatus = %s"
            params.append(filters["status"])

        # Search Term Filter
        if filters["search_term"]:
            query += " AND (Description LIKE %s OR PaidTo LIKE %s)"
            params.extend(
                [f"%{filters['search_term']}%", f"%{filters['search_term']}%"]
            )

        query += " ORDER BY ExpenseDate DESC"
        self.expenses_data = fetch_data(query, tuple(params))

    def render(self):
        """Main render method that routes to the correct view (list or form)."""
        st.title("💸 Expense Management")

        self._get_filtered_data()
        self._render_sidebar_filters()

        if st.session_state.editing_expense_id is not None:
            self._render_expense_form(st.session_state.editing_expense_id)
        else:
            self._render_main_view()

    def _render_sidebar_filters(self):
        """Renders filter widgets in the sidebar."""
        st.sidebar.header("Expense Filters")

        # Role-based access demo
        st.sidebar.selectbox(
            "Select User Role (Demo)",
            ["Admin", "Manager", "Employee"],
            key="expense_user_role",
        )
        st.sidebar.markdown("---")

        # Filters
        filters = st.session_state.expense_filters
        filters["search_term"] = st.sidebar.text_input(
            "Search Description/Payee", filters["search_term"]
        )
        filters["date_range"] = st.sidebar.date_input(
            "Date Range", value=filters["date_range"]
        )
        filters["category"] = st.sidebar.selectbox(
            "Category",
            [
                "All",
                "Rent",
                "Salary",
                "Utilities",
                "Purchase",
                "Marketing",
                "Travel",
                "Other",
            ],
            index=[
                "All",
                "Rent",
                "Salary",
                "Utilities",
                "Purchase",
                "Marketing",
                "Travel",
                "Other",
            ].index(filters["category"]),
        )
        filters["status"] = st.sidebar.selectbox(
            "Approval Status",
            ["All", "Pending", "Approved", "Rejected"],
            index=["All", "Pending", "Approved", "Rejected"].index(filters["status"]),
        )

    def _render_main_view(self):
        """Displays KPIs, charts, and the list of expenses."""
        self._render_kpis()
        st.markdown("---")
        self._render_charts()
        st.markdown("---")
        self._render_expense_list()

    def _render_kpis(self):
        """Displays key performance indicators in styled cards."""
        st.subheader("Financial Overview")
        if self.expenses_data.empty:
            st.info("No expense data available for the selected filters.")
            return

        total_expenses = self.expenses_data["Amount"].sum()
        pending_count = len(
            self.expenses_data[self.expenses_data["ApprovalStatus"] == "Pending"]
        )
        highest_category = (
            self.expenses_data.groupby("Category")["Amount"].sum().idxmax()
        )

        kpi_cols = st.columns(3)
        kpi_cols[0].metric("Total Expenses", f"Rs {total_expenses:,.2f}")
        kpi_cols[1].metric("Pending Approvals", f"{pending_count} Expenses")
        kpi_cols[2].metric("Top Spending Category", highest_category)

    def _render_charts(self):
        """Renders interactive charts for expense analytics."""
        st.subheader("Expense Analytics")
        if self.expenses_data.empty:
            return

        chart_cols = st.columns(2)
        with chart_cols[0]:
            category_data = (
                self.expenses_data.groupby("Category")["Amount"].sum().reset_index()
            )
            fig_cat = px.pie(
                category_data,
                names="Category",
                values="Amount",
                title="Expenses by Category",
                hole=0.3,
            )
            st.plotly_chart(fig_cat, use_container_width=True)

        with chart_cols[1]:
            method_data = (
                self.expenses_data.groupby("PaymentMethod")["Amount"]
                .sum()
                .reset_index()
            )
            fig_method = px.bar(
                method_data,
                x="PaymentMethod",
                y="Amount",
                title="Expenses by Payment Method",
                color="PaymentMethod",
            )
            st.plotly_chart(fig_method, use_container_width=True)

    def _render_expense_list(self):
        """Displays the list of expenses with action buttons."""
        list_cols = st.columns([4, 1])
        with list_cols[0]:
            st.subheader("Expense Records")
        with list_cols[1]:
            if st.button("➕ Add Expense", use_container_width=True):
                st.session_state.editing_expense_id = "new"
                st.rerun()

        if self.expenses_data.empty:
            st.warning("No expenses match the current filters.")
            return

        for _, expense in self.expenses_data.iterrows():
            self._render_expense_row(expense)

    def _render_expense_row(self, expense):
        """Renders a single row for an expense."""
        status_colors = {"Pending": "orange", "Approved": "green", "Rejected": "red"}
        status_color = status_colors.get(expense["ApprovalStatus"], "gray")

        st.markdown("---")
        main_cols = st.columns([3, 1.5, 1.5, 2])

        with main_cols[0]:
            st.markdown(f"**{expense['Description']}**")
            st.caption(
                f"Category: {expense['Category']} | Paid to: {expense.get('PaidTo', 'N/A')}"
            )
        with main_cols[1]:
            st.markdown(f"**Amount:** Rs {expense['Amount']:,.2f}")
            st.caption(f"Date: {expense['ExpenseDate'].strftime('%b %d, %Y')}")
        with main_cols[2]:
            st.markdown(f"**Status:** :{status_color}[{expense['ApprovalStatus']}]")
            st.caption(f"Method: {expense['PaymentMethod']}")
        with main_cols[3]:
            action_cols = st.columns(4)
            if action_cols[0].button(
                "✏️", key=f"edit_{expense['ExpenseID']}", help="Edit"
            ):
                st.session_state.editing_expense_id = expense["ExpenseID"]
                st.rerun()

            if st.session_state.expense_user_role in ["Admin", "Manager"]:
                if action_cols[1].button(
                    "🗑️", key=f"del_{expense['ExpenseID']}", help="Delete"
                ):
                    # Placeholder for a confirmation modal
                    if execute_query(
                        "DELETE FROM expenses WHERE ExpenseID = %s",
                        (expense["ExpenseID"],),
                    ):
                        st.toast("Expense deleted!", icon="✅")
                        st.rerun()

                if expense["ApprovalStatus"] == "Pending":
                    if action_cols[2].button(
                        "👍", key=f"appr_{expense['ExpenseID']}", help="Approve"
                    ):
                        execute_query(
                            "UPDATE expenses SET ApprovalStatus='Approved', ApprovedBy=%s WHERE ExpenseID=%s",
                            ("Admin User", expense["ExpenseID"]),
                        )
                        st.toast("Expense Approved!", icon="👍")
                        st.rerun()
                    if action_cols[3].button(
                        "👎", key=f"rej_{expense['ExpenseID']}", help="Reject"
                    ):
                        execute_query(
                            "UPDATE expenses SET ApprovalStatus='Rejected', ApprovedBy=%s WHERE ExpenseID=%s",
                            ("Admin User", expense["ExpenseID"]),
                        )
                        st.toast("Expense Rejected.", icon="👎")
                        st.rerun()

    def _render_expense_form(self, expense_id):
        """Renders a form for adding or editing an expense."""
        is_edit = expense_id != "new"
        title = "Edit Expense" if is_edit else "➕ Add New Expense"
        expense_data = {}
        if is_edit:
            expense_data = (
                self.expenses_data[self.expenses_data["ExpenseID"] == expense_id]
                .iloc[0]
                .to_dict()
            )

        with st.form("expense_form"):
            st.subheader(title)

            # --- Form Fields ---
            description = st.text_input(
                "Description*", value=expense_data.get("Description", "")
            )
            category = st.selectbox(
                "Category*",
                [
                    "Rent",
                    "Salary",
                    "Utilities",
                    "Purchase",
                    "Marketing",
                    "Travel",
                    "Other",
                ],
                index=[
                    "Rent",
                    "Salary",
                    "Utilities",
                    "Purchase",
                    "Marketing",
                    "Travel",
                    "Other",
                ].index(expense_data.get("Category", "Utilities")),
            )

            form_cols1 = st.columns(3)
            amount = form_cols1[0].number_input(
                "Amount*",
                min_value=0.0,
                value=float(expense_data.get("Amount", 0.0)),
                format="%.2f",
            )
            tax_rate = form_cols1[1].number_input(
                "Tax Rate (%)",
                min_value=0.0,
                value=float(expense_data.get("TaxRate", 0.0)),
                format="%.2f",
            )
            tax_amount = amount * (tax_rate / 100)
            form_cols1[2].metric("Total (inc. Tax)", f"Rs {amount + tax_amount:,.2f}")

            form_cols2 = st.columns(2)
            expense_date = form_cols2[0].date_input(
                "Expense Date",
                value=pd.to_datetime(
                    expense_data.get("ExpenseDate", date.today())
                ).date(),
            )
            payment_method = form_cols2[1].selectbox(
                "Payment Method",
                ["Cash", "Card", "Bank Transfer", "Online"],
                index=["Cash", "Card", "Bank Transfer", "Online"].index(
                    expense_data.get("PaymentMethod", "Card")
                ),
            )
            paid_to = st.text_input(
                "Paid To / Vendor", value=expense_data.get("PaidTo", "")
            )

            # --- File Attachments ---
            st.markdown("**Attachments**")
            uploaded_files = st.file_uploader(
                "Upload receipts or invoices", accept_multiple_files=True
            )
            existing_attachments = json.loads(expense_data.get("Attachments", "[]"))
            if existing_attachments:
                st.write("Current Attachments:")
                for att in existing_attachments:
                    st.markdown(
                        f"- [{os.path.basename(att)}]({att})"
                    )  # This needs a web server to work properly for download links

            notes = st.text_area("Notes", value=expense_data.get("Notes", ""))

            # --- Form Actions ---
            btn_cols = st.columns([1, 1, 5])
            if btn_cols[0].form_submit_button(
                "Save", type="primary", use_container_width=True
            ):
                if not description or amount <= 0:
                    st.error("Description and a valid Amount are required.")
                else:
                    # Handle file saving
                    new_attachment_paths = existing_attachments
                    for uploaded_file in uploaded_files:
                        file_path = os.path.join(ATTACHMENT_DIR, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        if file_path not in new_attachment_paths:
                            new_attachment_paths.append(file_path)

                    params = (
                        description,
                        category,
                        amount,
                        expense_date,
                        payment_method,
                        paid_to,
                        json.dumps(new_attachment_paths),
                        tax_rate,
                        tax_amount,
                        notes,
                    )
                    if is_edit:
                        query = "UPDATE expenses SET Description=%s, Category=%s, Amount=%s, ExpenseDate=%s, PaymentMethod=%s, PaidTo=%s, Attachments=%s, TaxRate=%s, TaxAmount=%s, Notes=%s WHERE ExpenseID=%s"
                        params += (expense_id,)
                    else:
                        query = "INSERT INTO expenses (Description, Category, Amount, ExpenseDate, PaymentMethod, PaidTo, Attachments, TaxRate, TaxAmount, Notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

                    if execute_query(query, params):
                        st.success(
                            f"Expense {'updated' if is_edit else 'saved'} successfully!"
                        )
                        st.session_state.editing_expense_id = None
                        st.rerun()

            if btn_cols[1].form_submit_button("Cancel", use_container_width=True):
                st.session_state.editing_expense_id = None
                st.rerun()
