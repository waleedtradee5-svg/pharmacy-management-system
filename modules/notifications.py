import streamlit as st
import pandas as pd
from db_connector import fetch_data, execute_query
from datetime import datetime, timedelta


class NotificationsManager:
    """
    Handles the generation, retrieval, and display of advanced, actionable system
    notifications with severity, categories, and deep integration.
    """

    TYPES = ["Low Stock", "Expiry Warning", "Outstanding Due", "Critical Stock"]
    CATEGORIES = ["Inventory", "Finance", "Sales", "HR", "System"]
    SEVERITIES = ["Low", "Medium", "High"]

    def __init__(self):
        """
        Initializes the manager, session state, and fetches configurable settings
        from the database for dynamic alert thresholds.
        """
        # Initialize session state for UI controls
        st.session_state.setdefault("notif_view_mode", "Unread")
        st.session_state.setdefault("notif_category_filter", ["All"])
        st.session_state.setdefault("notif_severity_filter", ["All"])
        st.session_state.setdefault("notif_search_keyword", "")

        # Fetch dynamic thresholds from the settings table
        settings = fetch_data(
            "SELECT key_name, value FROM settings WHERE key_name LIKE 'notification_%'"
        )
        settings_dict = (
            pd.Series(settings.value.values, index=settings.key_name).to_dict()
            if not settings.empty
            else {}
        )
        self.low_stock_threshold = int(
            settings_dict.get("notification_low_stock_threshold", 10)
        )
        self.high_sev_stock_threshold = int(
            settings_dict.get("notification_high_severity_stock_threshold", 5)
        )
        self.expiry_warning_days = int(
            settings_dict.get("notification_expiry_warning_days", 30)
        )

    # ---------------- Notification Generation ----------------
    def generate_notifications(self):
        """Orchestrates the creation of all types of system notifications."""
        self._generate_inventory_alerts()
        self._generate_finance_alerts()

    def _generate_inventory_alerts(self):
        """Generates notifications for low stock and expiring medicines."""
        medicines = fetch_data(
            "SELECT MedicineID, MedicineName, StockQty, ExpiryDate FROM medicines WHERE IsActive=TRUE"
        )
        if medicines.empty:
            return

        # Low Stock Alerts
        low_stock_medicines = medicines[
            medicines["StockQty"] <= self.low_stock_threshold
        ]
        for _, row in low_stock_medicines.iterrows():
            severity = (
                "High" if row["StockQty"] <= self.high_sev_stock_threshold else "Medium"
            )
            message = f"Low stock: '{row['MedicineName']}' has only {row['StockQty']} units left."
            self._create_notification_if_not_exists(
                "Low Stock",
                message,
                "Inventory",
                severity,
                "medicines",
                row["MedicineID"],
            )

        # Expiry Alerts
        if (
            "ExpiryDate" in medicines.columns
            and not medicines["ExpiryDate"].isnull().all()
        ):
            medicines["ExpiryDate"] = pd.to_datetime(medicines["ExpiryDate"])
            expiry_limit = datetime.now().date() + timedelta(
                days=self.expiry_warning_days
            )
            near_expiry = medicines[
                (medicines["ExpiryDate"].dt.date <= expiry_limit)
                & (medicines["ExpiryDate"].dt.date >= datetime.now().date())
            ]
            for _, row in near_expiry.iterrows():
                days_left = (row["ExpiryDate"].date() - datetime.now().date()).days
                severity = "High" if days_left <= 7 else "Medium"
                message = f"Expiry warning: '{row['MedicineName']}' will expire in {days_left} days on {row['ExpiryDate'].strftime('%Y-%m-%d')}."
                self._create_notification_if_not_exists(
                    "Expiry Warning",
                    message,
                    "Inventory",
                    severity,
                    "medicines",
                    row["MedicineID"],
                )

    def _generate_finance_alerts(self):
        """Generates notifications for customers with outstanding dues."""
        customers = fetch_data(
            "SELECT id, name, outstanding_amount FROM customers WHERE outstanding_amount > 0 AND status = 'Active'"
        )
        for _, row in customers.iterrows():
            message = f"Pending payment from '{row['name']}' of Rs {row['outstanding_amount']:,.2f}."
            self._create_notification_if_not_exists(
                "Outstanding Due", message, "Finance", "Medium", "customers", row["id"]
            )

    def _create_notification_if_not_exists(
        self, n_type, message, category, severity, table, rel_id
    ):
        """Creates a notification only if an unread one for the same issue doesn't already exist."""
        exists = fetch_data(
            "SELECT NotificationID FROM notifications WHERE Type=%s AND RelatedTable=%s AND RelatedID=%s AND Status='Unread'",
            (n_type, table, int(rel_id)),
        )
        if exists.empty:
            execute_query(
                "INSERT INTO notifications (Type, Message, category, severity, RelatedTable, RelatedID) VALUES (%s, %s, %s, %s, %s, %s)",
                (n_type, message, category, severity, table, int(rel_id)),
            )

    # ---------------- Data Fetching & Actions ----------------
    def get_notifications(
        self, status=None, categories=None, severities=None, keyword=None
    ):
        """
        Fetches notifications with advanced, optional filters. This is the central
        data retrieval method for the module.
        """
        query = "SELECT * FROM notifications WHERE 1=1"
        params = []

        if status and status != "All":
            query += " AND Status = %s"
            params.append(status)
        if categories and "All" not in categories:
            query += f" AND category IN ({','.join(['%s'] * len(categories))})"
            params.extend(categories)
        if severities and "All" not in severities:
            query += f" AND severity IN ({','.join(['%s'] * len(severities))})"
            params.extend(severities)
        if keyword:
            query += " AND Message LIKE %s"
            params.append(f"%{keyword.strip()}%")

        query += " ORDER BY CreatedAt DESC"
        return fetch_data(query, tuple(params))

    def get_unread_notifications(self):
        """
        A specific method to quickly fetch only unread notifications. It calls the main
        get_notifications method with a fixed status filter.
        """
        return self.get_notifications(status="Unread")

    def mark_as_read(self, notification_id):
        """Marks a specific notification as 'Read'."""
        execute_query(
            "UPDATE notifications SET Status='Read' WHERE NotificationID=%s",
            (int(notification_id),),
        )

    def mark_all_as_read(self):
        """Marks all 'Unread' notifications as 'Read'."""
        execute_query("UPDATE notifications SET Status='Read' WHERE Status='Unread'")

    # ---------------- UI Rendering ----------------
    def _render_filters(self):
        """Renders the filter controls for the notification list."""
        cols = st.columns([1.5, 1.5, 1.5, 2, 1.5])
        cols[0].radio("View", ["Unread", "All"], key="notif_view_mode", horizontal=True)
        cols[1].multiselect(
            "Category", ["All"] + self.CATEGORIES, key="notif_category_filter"
        )
        cols[2].multiselect(
            "Severity", ["All"] + self.SEVERITIES, key="notif_severity_filter"
        )
        cols[3].text_input(
            "Search Message",
            key="notif_search_keyword",
            placeholder="e.g., Paracetamol",
        )

        # Place button in the last column for better alignment
        with cols[4]:
            st.write("")  # Spacer for vertical alignment
            if st.button("Mark All as Read", use_container_width=True):
                self.mark_all_as_read()
                st.rerun()

    def _render_analytics(self, notifications_df):
        """Renders simple charts for notification analytics."""
        st.write("### Notification Analytics")
        if not notifications_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Breakdown by Category**")
                st.bar_chart(notifications_df["category"].value_counts())
            with c2:
                st.write("**Breakdown by Severity**")
                st.bar_chart(notifications_df["severity"].value_counts())
        else:
            st.info("No data available to display analytics.")

    def render(self):
        """Renders the full, interactive notification center UI."""
        st.title("🔔 Notification Center")
        st.write("Central hub for all system alerts and actionable insights.")

        self._render_filters()

        notifications_to_display = self.get_notifications(
            status=st.session_state.notif_view_mode,
            categories=st.session_state.notif_category_filter,
            severities=st.session_state.notif_severity_filter,
            keyword=st.session_state.notif_search_keyword,
        )

        st.markdown("---")
        if notifications_to_display is not None and not notifications_to_display.empty:
            st.write(f"#### Displaying {len(notifications_to_display)} Notifications")
            for _, notif in notifications_to_display.iterrows():
                icon = {"High": "🚨", "Medium": "⚠️", "Low": "ℹ️"}.get(
                    notif["severity"], ""
                )
                with st.container():
                    cols = st.columns([5, 1.5])
                    with cols[0]:
                        st.markdown(
                            f"**{icon} {notif['Type']}** `[{notif['category']}]` `[{notif['severity']}]`"
                        )
                        st.write(notif["Message"])
                        st.caption(
                            f"Received: {pd.to_datetime(notif['CreatedAt']).strftime('%b %d, %Y %I:%M %p')}"
                        )
                    with cols[1]:
                        # In-App Action Buttons
                        action_title = (
                            "View Item"
                            if notif["RelatedTable"] == "medicines"
                            else "View Customer"
                        )
                        target_module = (
                            "Inventory"
                            if notif["RelatedTable"] == "medicines"
                            else "Customers"
                        )
                        if st.button(
                            action_title,
                            key=f"view_{notif['RelatedTable']}_{notif['NotificationID']}",
                            use_container_width=True,
                        ):
                            st.session_state.navigate_to = target_module
                            st.session_state.navigate_to_item_id = notif["RelatedID"]
                            st.rerun()

                        if notif["Status"] == "Unread":
                            if st.button(
                                "Mark as Read",
                                key=f"read_{notif['NotificationID']}",
                                use_container_width=True,
                            ):
                                self.mark_as_read(notif["NotificationID"])
                                st.rerun()
        else:
            st.success("No notifications match the current filters. All clear! ✅")

        st.markdown("---")
        self._render_analytics(notifications_to_display)
