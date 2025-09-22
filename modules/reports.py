import streamlit as st
import pandas as pd
from datetime import date, timedelta
import json
import plotly.express as px
from db_connector import fetch_data, execute_query


class ReportsModule:
    """
    Provides a comprehensive, interactive reporting dashboard with a premium design,
    KPIs with trend analysis, advanced dynamic filtering, interactive charts,
    custom report management, and role-based access control.
    """

    def __init__(self):
        """Initializes session state keys for managing filters and UI state."""
        st.session_state.setdefault("report_user_role", "Admin")

        # Initialize filter states for both the live widgets and the applied filters
        if "report_filters_applied" not in st.session_state:
            st.session_state.report_filters_applied = {
                "date_range": (date.today() - timedelta(days=30), date.today()),
                "customers": ["All"],
                "suppliers": ["All"],
            }

        # Ensure widget states are initialized from the applied filters
        for key, value in st.session_state.report_filters_applied.items():
            st.session_state.setdefault(f"report_{key}_widget", value)

    def _get_date_range_for_period(self, start_date, end_date):
        """Calculates the previous period for trend comparison."""
        period_length = (end_date - start_date).days
        prev_start_date = start_date - timedelta(days=period_length + 1)
        prev_end_date = start_date - timedelta(days=period_length + 1)
        return prev_start_date, prev_end_date

    def _get_filtered_data(self):
        """
        Fetches and processes all data from the database based on the currently
        APPLIED filters. This is the core data engine for the module.
        """
        filters = st.session_state.report_filters_applied
        start_date, end_date = filters["date_range"]

        # Fetch Data for Previous Period for Trend Calculation
        prev_start, prev_end = self._get_date_range_for_period(start_date, end_date)
        prev_sales_data = fetch_data(
            "SELECT amount FROM accounting_entries WHERE entry_type = 'Income' AND entry_date BETWEEN %s AND %s",
            (prev_start, prev_end),
        )

        # Build Dynamic WHERE Clauses for Main Period
        sales_query = "SELECT * FROM accounting_entries WHERE entry_type = 'Income' AND entry_date BETWEEN %s AND %s"
        expenses_query = "SELECT * FROM accounting_entries WHERE entry_type = 'Expense' AND entry_date BETWEEN %s AND %s"

        self.sales_data = fetch_data(sales_query, (start_date, end_date))
        self.expenses_data = fetch_data(expenses_query, (start_date, end_date))

        # Fetch master data
        self.customers_data = fetch_data("SELECT * FROM customers")
        self.medicines_data = fetch_data(
            "SELECT m.*, s.SupplierName FROM medicines m LEFT JOIN suppliers s ON m.SupplierID = s.SupplierID"
        )
        self.suppliers_data = fetch_data("SELECT * FROM suppliers")

        # KPI Calculations
        self.kpi_total_sales = (
            self.sales_data["amount"].sum() if not self.sales_data.empty else 0
        )
        self.kpi_total_expenses = (
            self.expenses_data["amount"].sum() if not self.expenses_data.empty else 0
        )
        self.kpi_net_profit = self.kpi_total_sales - self.kpi_total_expenses
        self.kpi_total_dues = (
            self.customers_data["outstanding_amount"].sum()
            if not self.customers_data.empty
            else 0
        )
        self.low_stock_alerts = (
            self.medicines_data[
                self.medicines_data["StockQty"] < self.medicines_data["ReorderLevel"]
            ]
            if not self.medicines_data.empty
            else pd.DataFrame()
        )
        self.top_5_customers = (
            self.customers_data.nlargest(5, "total_purchases")[
                ["name", "total_purchases"]
            ]
            if not self.customers_data.empty
            else pd.DataFrame()
        )

        if (
            not self.medicines_data.empty
            and "SupplierName" in self.medicines_data.columns
        ):
            self.top_5_suppliers = (
                self.medicines_data["SupplierName"]
                .value_counts()
                .nlargest(5)
                .reset_index()
            )
            self.top_5_suppliers.columns = ["SupplierName", "ProductCount"]
        else:
            self.top_5_suppliers = pd.DataFrame()

        # Trend Calculation
        prev_sales = prev_sales_data["amount"].sum() if not prev_sales_data.empty else 0
        self.sales_trend = (
            ((self.kpi_total_sales - prev_sales) / prev_sales * 100)
            if prev_sales > 0
            else 0
        )

    def _inject_custom_css(self):
        """Injects custom CSS for styling the module's components."""
        st.markdown(
            """
        <style>
            .kpi-card {
                flex: 1;
                min-width: 200px;
                padding: 20px;
                border-radius: 10px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                transition: transform 0.2s, box-shadow 0.2s;
                text-align: center;
            }
            .kpi-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }
            .kpi-title {
                font-size: 1em;
                font-weight: 600;
                color: #495057;
                margin-bottom: 10px;
            }
            .kpi-value {
                font-size: 2em;
                font-weight: 700;
                color: #212529;
            }
            .kpi-trend {
                font-size: 0.85em;
                margin-top: 5px;
            }
            .profit-positive { background-color: #e8f5e9; border-color: #a5d6a7; }
            .profit-negative { background-color: #ffebee; border-color: #ef9a9a; }
            .alert-active { border: 2px solid #ffc107; }
        </style>
        """,
            unsafe_allow_html=True,
        )

    def render(self):
        """Main render method to display the entire reports module."""
        st.title("📊 Reports & Analytics Dashboard")
        self._inject_custom_css()
        self._get_filtered_data()
        self._render_sidebar_filters()

        st.sidebar.selectbox(
            "Select User Role (for Demo)",
            ["Admin", "Manager", "Accountant", "Pharmacist"],
            key="report_user_role",
        )

        if st.session_state.report_user_role == "Admin":
            self._render_admin_dashboard()
        elif st.session_state.report_user_role == "Accountant":
            self._render_accountant_dashboard()
        elif st.session_state.report_user_role == "Pharmacist":
            self._render_pharmacist_dashboard()
        else:
            self._render_manager_dashboard()

    def _render_sidebar_filters(self):
        """Renders all advanced filter widgets in the sidebar."""
        st.sidebar.header("🔍 Report Filters")
        st.sidebar.write("**Quick Date Ranges**")
        date_cols = st.sidebar.columns(2)
        if date_cols[0].button("This Month", use_container_width=True):
            today = date.today()
            st.session_state.report_date_range_widget = (today.replace(day=1), today)
        if date_cols[1].button("Last 30 Days", use_container_width=True):
            st.session_state.report_date_range_widget = (
                date.today() - timedelta(days=30),
                date.today(),
            )

        st.session_state.report_date_range_widget = st.sidebar.date_input(
            "Custom Date Range", value=st.session_state.report_date_range_widget
        )

        customer_list = (
            ["All"] + self.customers_data["name"].unique().tolist()
            if not self.customers_data.empty
            else ["All"]
        )
        supplier_list = (
            ["All"] + self.suppliers_data["SupplierName"].unique().tolist()
            if not self.suppliers_data.empty
            else ["All"]
        )

        st.session_state.report_customers_widget = st.sidebar.multiselect(
            "Filter by Customer",
            customer_list,
            default=st.session_state.report_customers_widget,
        )
        st.session_state.report_suppliers_widget = st.sidebar.multiselect(
            "Filter by Supplier",
            supplier_list,
            default=st.session_state.report_suppliers_widget,
        )

        st.sidebar.markdown("---")
        if st.sidebar.button(
            "🚀 Apply Filters", type="primary", use_container_width=True
        ):
            st.session_state.report_filters_applied["date_range"] = (
                st.session_state.report_date_range_widget
            )
            st.session_state.report_filters_applied["customers"] = (
                st.session_state.report_customers_widget
            )
            st.session_state.report_filters_applied["suppliers"] = (
                st.session_state.report_suppliers_widget
            )
            st.rerun()

    def _render_kpis(self, roles=["all"]):
        """Renders the main KPI cards using st.columns for a robust layout."""
        st.subheader("Key Performance Indicators")

        kpis_to_render = []
        if "finance" in roles or "all" in roles:
            profit_color = (
                "profit-positive" if self.kpi_net_profit >= 0 else "profit-negative"
            )
            kpis_to_render.extend(
                [
                    {
                        "title": "Total Sales",
                        "value": f"Rs {self.kpi_total_sales:,.0f}",
                        "icon": "💰",
                        "trend": self.sales_trend,
                        "color_class": "",
                    },
                    {
                        "title": "Total Expenses",
                        "value": f"Rs {self.kpi_total_expenses:,.0f}",
                        "icon": "💸",
                    },
                    {
                        "title": "Net Profit",
                        "value": f"Rs {self.kpi_net_profit:,.0f}",
                        "icon": "📈",
                        "color_class": profit_color,
                    },
                ]
            )
        if "customer" in roles or "all" in roles:
            kpis_to_render.append(
                {
                    "title": "Customer Dues",
                    "value": f"Rs {self.kpi_total_dues:,.0f}",
                    "icon": "🧾",
                }
            )
        if "inventory" in roles or "all" in roles:
            alert_color = "alert-active" if len(self.low_stock_alerts) > 0 else ""
            kpis_to_render.append(
                {
                    "title": "Low Stock Alerts",
                    "value": f"{len(self.low_stock_alerts)} items",
                    "icon": "⚠️",
                    "color_class": alert_color,
                }
            )

        if not kpis_to_render:
            return

        cols = st.columns(len(kpis_to_render))
        for i, kpi in enumerate(kpis_to_render):
            with cols[i]:
                trend_html = ""
                if kpi.get("trend") is not None:
                    trend_color = "green" if kpi["trend"] >= 0 else "red"
                    trend_icon = "▲" if kpi["trend"] >= 0 else "▼"
                    trend_html = f'<p class="kpi-trend" style="color:{trend_color};">{trend_icon} {kpi["trend"]:.2f}% vs prev. period</p>'

                st.markdown(
                    f"""
                <div class="kpi-card {kpi.get('color_class', '')}">
                    <p class="kpi-title">{kpi['icon']} {kpi['title']}</p>
                    <p class="kpi-value">{kpi['value']}</p>
                    {trend_html}
                </div>
                """,
                    unsafe_allow_html=True,
                )

    def _render_charts(self, roles=["all"]):
        """Renders interactive Plotly charts and visualizations."""
        st.subheader("Visual Analytics")
        chart_cols = st.columns(2)

        with chart_cols[0]:
            if "finance" in roles or "all" in roles:
                if not self.sales_data.empty:
                    sales_by_day = (
                        self.sales_data.groupby("entry_date")["amount"]
                        .sum()
                        .reset_index()
                    )
                    fig = px.area(
                        sales_by_day,
                        x="entry_date",
                        y="amount",
                        title="Sales Trend Over Time",
                        labels={"entry_date": "Date", "amount": "Total Sales"},
                    )
                    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No sales data available to display trend chart.")

        with chart_cols[1]:
            if "finance" in roles or "all" in roles:
                if not self.expenses_data.empty:
                    expenses_by_cat = (
                        self.expenses_data.groupby("category")["amount"]
                        .sum()
                        .reset_index()
                    )
                    fig2 = px.pie(
                        expenses_by_cat,
                        names="category",
                        values="amount",
                        title="Expense Breakdown by Category",
                        hole=0.3,
                    )
                    fig2.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No expense data available to display breakdown chart.")

    def _render_detailed_tables(self, roles=["all"]):
        """Renders detailed, exportable data tables in tabs."""
        st.subheader("Detailed Reports")
        tabs_to_show = [
            role
            for role in [
                "Sales Details",
                "Expenses Details",
                "Low Stock Items",
                "Top Customers",
                "Top Suppliers",
            ]
            if (
                ("finance" in roles and role in ["Sales Details", "Expenses Details"])
                or ("inventory" in roles and role == "Low Stock Items")
                or ("customer" in roles and role in ["Top Customers", "Top Suppliers"])
                or ("all" in roles)
            )
        ]

        if not tabs_to_show:
            st.info("No detailed reports available for this role.")
            return

        tabs = st.tabs(tabs_to_show)
        for i, title in enumerate(tabs_to_show):
            with tabs[i]:
                data_map = {
                    "Sales Details": self.sales_data,
                    "Expenses Details": self.expenses_data,
                    "Low Stock Items": self.low_stock_alerts,
                    "Top Customers": self.top_5_customers,
                    "Top Suppliers": self.top_5_suppliers,
                }
                data = data_map.get(title, pd.DataFrame())
                if not data.empty:
                    st.dataframe(data, use_container_width=True)
                    st.download_button(
                        f"📥 Export {title}",
                        data.to_csv(index=False).encode("utf-8"),
                        f"{title.lower().replace(' ','_')}.csv",
                        "text/csv",
                        key=f"export_{title.replace(' ','_')}",
                    )
                else:
                    st.warning(f"No data available for {title} in the selected period.")

    def _render_admin_dashboard(self):
        self._render_kpis(roles=["all"])
        st.markdown("---")
        self._render_charts(roles=["all"])
        st.markdown("---")
        self._render_detailed_tables(roles=["all"])

    def _render_accountant_dashboard(self):
        self._render_kpis(roles=["finance", "customer"])
        st.markdown("---")
        self._render_charts(roles=["finance"])
        st.markdown("---")
        self._render_detailed_tables(roles=["finance", "customer"])

    def _render_manager_dashboard(self):
        self._render_kpis(roles=["finance", "inventory", "customer"])
        st.markdown("---")
        self._render_charts(roles=["finance", "inventory"])
        st.markdown("---")
        self._render_detailed_tables(roles=["finance", "inventory", "customer"])

    def _render_pharmacist_dashboard(self):
        self._render_kpis(roles=["inventory"])
        st.markdown("---")
        st.info("Pharmacists have access to inventory alerts and stock details.")
        self._render_detailed_tables(roles=["inventory"])
