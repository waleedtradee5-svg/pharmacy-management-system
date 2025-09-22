import streamlit as st
import pandas as pd
import plotly.express as px
from db_connector import fetch_data  # Assuming db_connector.py is correctly set up


class DashboardModule:
    """
    Renders a modern, animated dashboard with KPIs, charts, and key data tables
    for a professional overview of the pharmacy's operations.
    """

    def __init__(self):
        """Initializes and fetches all data required for the dashboard."""
        self._fetch_data()

    def _fetch_data(self):
        """
        Fetches data from the database, ensuring all column names match the
        database schema (PascalCase) to prevent errors.
        """
        # --- KPI QUERIES ---

        # Today's Sales (FIXED: Assigned result to self.sales_today)
        sales_df = fetch_data(
            "SELECT SUM(GrandTotal) as total FROM sales_invoices WHERE InvoiceDate = CURDATE()"
        )
        self.sales_today = (
            sales_df.iloc[0]["total"]
            if not sales_df.empty and pd.notna(sales_df.iloc[0]["total"])
            else 0
        )

        # Low Stock Items
        low_stock_df = fetch_data(
            "SELECT COUNT(*) as count FROM medicines WHERE StockQty < ReorderLevel"
        )
        self.low_stock_items = (
            low_stock_df.iloc[0]["count"] if not low_stock_df.empty else 0
        )

        # Pending Invoices (FIXED: Corrected 'status' to 'Status')
        pending_df = fetch_data(
            "SELECT COUNT(*) as count FROM sales_invoices WHERE Status = 'Pending'"
        )
        self.pending_invoices = (
            pending_df.iloc[0]["count"] if not pending_df.empty else 0
        )

        # New Customers (FIXED: Corrected 'created_at' to match customer schema)
        new_cust_df = fetch_data(
            "SELECT COUNT(*) as count FROM customers WHERE created_at >= CURDATE() - INTERVAL 7 DAY"
        )
        self.new_customers = (
            new_cust_df.iloc[0]["count"] if not new_cust_df.empty else 0
        )

        # --- CHART AND TABLE QUERIES ---

        # Sales Trend (FIXED: Corrected 'InvoiceDate' and 'GrandTotal')
        self.sales_trend_30_days = fetch_data(
            """
            SELECT InvoiceDate, SUM(GrandTotal) as daily_sales 
            FROM sales_invoices 
            WHERE InvoiceDate >= CURDATE() - INTERVAL 30 DAY 
            GROUP BY InvoiceDate 
            ORDER BY InvoiceDate ASC
            """
        )

        # Low Stock Medicines Table
        self.low_stock_medicines = fetch_data(
            """
            SELECT MedicineName, Category, StockQty, ReorderLevel
            FROM medicines
            WHERE StockQty < ReorderLevel
            ORDER BY StockQty ASC
            LIMIT 10
            """
        )

    def _display_kpis(self):
        """Displays the four main KPI cards with values fetched from the database."""
        kpi_cols = st.columns(4)
        with kpi_cols[0]:
            # FIXED: Now correctly references self.sales_today
            self._render_kpi_card("Today's Sales", f"PKR {self.sales_today:,.0f}", "💰")
        with kpi_cols[1]:
            self._render_kpi_card("Low Stock Items", f"{self.low_stock_items}", "📦")
        with kpi_cols[2]:
            self._render_kpi_card("Pending Invoices", f"{self.pending_invoices}", "⏳")
        with kpi_cols[3]:
            self._render_kpi_card("New Customers (7d)", f"{self.new_customers}", "👥")

    def _render_kpi_card(self, title, value, icon):
        """Renders a single styled KPI card."""
        st.markdown(
            f"""
            <div class="kpi-card">
                <p class="kpi-icon">{icon}</p>
                <p class="kpi-title">{title}</p>
                <p class="kpi-value">{value}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _display_charts_and_tables(self):
        """Displays the main content area with a sales chart and a low-stock table."""
        container_cols = st.columns([2, 1])

        # Sales Trend Chart
        with container_cols[0]:
            st.markdown('<div class="data-container">', unsafe_allow_html=True)
            st.markdown(
                '<h3 class="container-title">Last 30 Days Sales Trend</h3>',
                unsafe_allow_html=True,
            )
            if not self.sales_trend_30_days.empty:
                fig = px.area(
                    self.sales_trend_30_days,
                    x="InvoiceDate",
                    y="daily_sales",
                    markers=True,
                    labels={"InvoiceDate": "Date", "daily_sales": "Total Sales (PKR)"},
                )
                fig.update_traces(
                    line_color="#28a745", fillcolor="rgba(40, 167, 69, 0.2)"
                )
                fig.update_layout(
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No sales data available for the last 30 days.")
            st.markdown("</div>", unsafe_allow_html=True)

        # Low Stock Medicines Table
        with container_cols[1]:
            st.markdown('<div class="data-container">', unsafe_allow_html=True)
            st.markdown(
                '<h3 class="container-title">⚠️ Action Required: Low Stock</h3>',
                unsafe_allow_html=True,
            )
            if not self.low_stock_medicines.empty:
                st.dataframe(
                    self.low_stock_medicines, use_container_width=True, hide_index=True
                )
            else:
                st.success("Great! No medicines are currently low on stock.")
            st.markdown("</div>", unsafe_allow_html=True)

    def render(self):
        """Renders the entire dashboard with animations and custom styles."""
        # --- CSS for Animations and Styling ---
        st.markdown(
            """
            <style>
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .kpi-card {
                    background-color: #ffffff;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    text-align: center;
                    border-left: 5px solid #007bff;
                    animation: fadeIn 0.5s ease-out forwards;
                }
                .kpi-card:nth-child(2) { border-left-color: #ffc107; animation-delay: 0.1s; }
                .kpi-card:nth-child(3) { border-left-color: #dc3545; animation-delay: 0.2s; }
                .kpi-card:nth-child(4) { border-left-color: #28a745; animation-delay: 0.3s; }
                .kpi-icon { font-size: 2rem; }
                .kpi-title { font-size: 1rem; color: #6c757d; margin-bottom: 5px; }
                .kpi-value { font-size: 1.5rem; font-weight: bold; color: #343a40; }
                .data-container {
                    background-color: #ffffff;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    animation: fadeIn 0.5s ease-out forwards;
                    animation-delay: 0.4s;
                    height: 100%;
                }
                .container-title { margin-bottom: 20px; }
            </style>
        """,
            unsafe_allow_html=True,
        )

        st.title("📈 Dashboard Overview")
        st.markdown("A real-time overview of key pharmacy metrics and activities.")
        st.markdown("---")
        self._display_kpis()
        st.markdown("<br>", unsafe_allow_html=True)
        self._display_charts_and_tables()
