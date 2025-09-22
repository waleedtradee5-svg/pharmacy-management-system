import streamlit as st

# A comment to force a redeployment
from streamlit_option_menu import option_menu

# --- Module Imports ---
# Ensure you have these files in your modules folder
from modules.dashboard import DashboardModule
from modules.customers import CustomersModule
from modules.inventory import InventoryModule
from modules.suppliers import SuppliersModule
from modules.reports import ReportsModule
from modules.notifications import NotificationsManager
from modules.expense import ExpensesModule
from modules.sales import SalesModule
from modules.purchase import PurchaseModule
from modules.crm import CrmCampaign

# --- Page Config ---
st.set_page_config(page_title="PharmaSuite ERP", page_icon="⚕️", layout="wide")


# --- Load Custom CSS ---
def load_css(file_name="style.css"):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(
            f"CSS file '{file_name}' not found. Please create it for custom styling."
        )


load_css()


# --- Main Application ---
class PharmacyERP:
    """
    The main class that orchestrates the entire ERP application, including
    module loading, navigation, and rendering.
    """

    def __init__(self):
        """Initializes all modules and sets up the application structure."""
        # Initialize notifications first to generate alerts on every page load
        self.notification_manager = NotificationsManager()
        self.notification_manager.generate_notifications()

        # --- Modules Dictionary ---
        # Add or remove modules here to control what appears in the ERP
        self.modules = {
            "Dashboard": DashboardModule(),
            "Customers": CustomersModule(),
            "Suppliers": SuppliersModule(),
            "Inventory": InventoryModule(),
            "Reports": ReportsModule(),
            "Expenses": ExpensesModule(),
            "Notifications": self.notification_manager,
            "Sales": SalesModule(),
            "Purchase": PurchaseModule(),
            "CRM": CrmCampaign(),
        }

        self.module_names = list(self.modules.keys())
        # Ensure the number of icons matches the number of modules
        self.module_icons = [
            "speedometer2",
            "people-fill",
            "truck",
            "boxes",
            "bar-chart-line-fill",
            "bell-fill",
            # "cart", "cart-check-fill", "megaphone-fill"
        ]

    def _render_notification_popover(self):
        """Renders the notification bell icon and a quick-view popover in the header."""
        # This now correctly calls the fixed method in NotificationsManager
        unread_notifications = self.notification_manager.get_unread_notifications()
        count = len(unread_notifications) if unread_notifications is not None else 0

        # The popover provides a quick glance at the latest notifications
        with st.popover("Notifications"):
            st.subheader(f"You have {count} unread notifications")
            st.markdown("---")
            if unread_notifications is not None and not unread_notifications.empty:
                for _, notif in unread_notifications.head(5).iterrows():  # Show top 5
                    st.info(notif["Message"])
                    if st.button(
                        "Mark as Read", key=f"popover_read_{notif['NotificationID']}"
                    ):
                        self.notification_manager.mark_as_read(notif["NotificationID"])
                        st.rerun()
                st.markdown("---")
                if st.button("View All Notifications"):
                    st.session_state.navigate_to = "Notifications"
                    st.rerun()
            else:
                st.success("No unread notifications.")

        # Display the bell icon with a notification badge
        badge_html = (
            f'<span class="notification-badge">{count}</span>' if count > 0 else ""
        )
        st.markdown(
            f"""
            <div class="notification-bell">
                🔔 {badge_html}
            </div>
        """,
            unsafe_allow_html=True,
        )

    def run(self):
        """The main method to run the ERP application's UI and logic."""
        # Render the top header with the title and notification bell
        header_cols = st.columns([4, 1])
        with header_cols[0]:
            st.markdown(
                '<h2 class="app-title">⚕️ PharmaSuite ERP</h2>', unsafe_allow_html=True
            )
        with header_cols[1]:
            self._render_notification_popover()

        # --- Cross-Module Navigation Logic ---
        # This checks if a notification button has requested a page change
        default_index = 0
        if (
            "navigate_to" in st.session_state
            and st.session_state.navigate_to in self.module_names
        ):
            default_index = self.module_names.index(st.session_state.navigate_to)
            # The 'navigate_to' key is deleted by the target module after it's used,
            # but we can also add a failsafe here if needed.

        # Render the sidebar navigation menu
        with st.sidebar:
            st.sidebar.header("Navigation")
            selected_module = option_menu(
                menu_title="Main Menu",
                options=self.module_names,
                icons=self.module_icons,
                menu_icon="cast",
                default_index=default_index,
                styles={
                    "container": {"padding": "5px"},
                    "nav-link": {
                        "font-size": "18px",
                        "text-align": "left",
                        "margin": "5px",
                        "border-radius": "10px",
                    },
                    "nav-link-selected": {"background-color": "#0d6efd"},
                },
            )

        # Render the content of the selected module
        if selected_module in self.modules:
            self.modules[selected_module].render()


# --- Entry Point ---
if __name__ == "__main__":
    # Inject some basic CSS for the notification bell if style.css is not comprehensive
    st.markdown(
        """
        <style>
        .notification-bell {
            font-size: 24px;
            cursor: pointer;
            position: relative;
            display: inline-block;
            float: right;
            margin-top: 10px;
        }
        .notification-badge {
            position: absolute;
            top: -5px;
            right: -10px;
            background-color: red;
            color: white;
            border-radius: 50%;
            padding: 2px 6px;
            font-size: 12px;
            font-weight: bold;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    app = PharmacyERP()
    app.run()
