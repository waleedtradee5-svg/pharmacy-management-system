import streamlit as st
import pandas as pd
from datetime import date
from db_connector import fetch_data, execute_query
import plotly.express as px


class CrmCampaign:
    """
    A comprehensive CRM and Campaign Management module for the PharmaSuite ERP.
    It handles campaigns, leads, interactions, and provides advanced analytics.
    """

    def __init__(self):
        """Initializes session state for filters, forms, and navigation."""
        st.session_state.setdefault("crm_user_role", "Admin")
        st.session_state.setdefault("editing_campaign_id", None)
        st.session_state.setdefault("adding_lead_to_campaign_id", None)
        st.session_state.setdefault("logging_interaction_for_lead_id", None)

    def _get_data(self):
        """Fetches all CRM-related data and calculates analytics."""
        self.campaigns = fetch_data("SELECT * FROM campaigns ORDER BY StartDate DESC")
        self.leads = fetch_data(
            "SELECT l.*, c.Name as CampaignName FROM leads l LEFT JOIN campaigns c ON l.CampaignID = c.CampaignID ORDER BY l.CreatedAt DESC"
        )
        self.interactions = fetch_data(
            "SELECT i.*, l.Name as LeadName FROM interactions i LEFT JOIN leads l ON i.LeadID = l.LeadID ORDER BY i.Date DESC"
        )

        # --- Analytics Calculation ---
        if not self.leads.empty:
            self.kpi_total_leads = len(self.leads)
            self.kpi_converted_leads = len(
                self.leads[self.leads["Status"] == "Converted"]
            )
            self.conversion_rate = (
                (self.kpi_converted_leads / self.kpi_total_leads * 100)
                if self.kpi_total_leads > 0
                else 0
            )

            self.leads_by_campaign = (
                self.leads.groupby("CampaignName")["LeadID"]
                .count()
                .reset_index()
                .rename(columns={"LeadID": "LeadCount"})
            )
            self.leads_by_status = self.leads["Status"].value_counts().reset_index()
        else:
            self.kpi_total_leads = 0
            self.kpi_converted_leads = 0
            self.conversion_rate = 0
            self.leads_by_campaign = pd.DataFrame()
            self.leads_by_status = pd.DataFrame()

    def render(self):
        """Main render method to display the CRM module UI."""
        self._get_data()
        st.title("🎯 CRM & Campaign Management")

        # Role-based access simulation
        st.sidebar.selectbox(
            "Select User Role (for Demo)",
            ["Admin", "Manager", "Sales"],
            key="crm_user_role",
        )

        # UI Routing
        if st.session_state.editing_campaign_id is not None:
            self._render_campaign_form(st.session_state.editing_campaign_id)
        elif st.session_state.adding_lead_to_campaign_id is not None:
            self._render_lead_form(st.session_state.adding_lead_to_campaign_id)
        elif st.session_state.logging_interaction_for_lead_id is not None:
            self._render_interaction_form(
                st.session_state.logging_interaction_for_lead_id
            )
        else:
            self._render_main_view()

    def _render_main_view(self):
        """Renders the main tabbed interface for the CRM module."""
        tabs = st.tabs(
            ["📊 Dashboard & Campaigns", "👥 Leads Management", "📞 Interaction Logs"]
        )

        with tabs[0]:
            self._render_dashboard_tab()
        with tabs[1]:
            self._render_leads_tab()
        with tabs[2]:
            self._render_interactions_tab()

    def _render_dashboard_tab(self):
        """Renders the main dashboard with KPIs, charts, and the campaign list."""
        st.subheader("Campaign Performance Overview")

        # KPIs
        kpi_cols = st.columns(3)
        kpi_cols[0].metric("Total Leads Generated", self.kpi_total_leads)
        kpi_cols[1].metric("Converted Leads", self.kpi_converted_leads)
        kpi_cols[2].metric("Overall Conversion Rate", f"{self.conversion_rate:.2f}%")

        st.markdown("---")

        # Analytics Charts
        chart_cols = st.columns(2)
        if not self.leads_by_campaign.empty:
            fig_leads = px.bar(
                self.leads_by_campaign,
                x="CampaignName",
                y="LeadCount",
                title="Leads per Campaign",
                labels={"LeadCount": "Number of Leads"},
            )
            chart_cols[0].plotly_chart(fig_leads, use_container_width=True)
        if not self.leads_by_status.empty:
            fig_status = px.pie(
                self.leads_by_status,
                names="Status",
                values="count",
                title="Lead Status Distribution",
                hole=0.4,
            )
            chart_cols[1].plotly_chart(fig_status, use_container_width=True)

        st.markdown("---")

        # Campaign List
        st.subheader("Manage Campaigns")
        if st.button("➕ Create New Campaign"):
            st.session_state.editing_campaign_id = "new"
            st.rerun()

        if not self.campaigns.empty:
            for _, campaign in self.campaigns.iterrows():
                self._render_campaign_row(campaign)

    def _render_campaign_row(self, campaign):
        """Renders a single campaign with details and action buttons."""
        st.markdown("---")
        status_color = {
            "Active": "green",
            "Completed": "blue",
            "Planned": "orange",
            "Paused": "gray",
        }.get(campaign["Status"], "gray")

        cols = st.columns([3, 2, 2])
        cols[0].markdown(f"**{campaign['Name']}**")
        cols[0].caption(campaign["Description"])
        cols[1].markdown(
            f"**Status:** <span style='color:{status_color};'>{campaign['Status']}</span>",
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            f"**Duration:** {campaign['StartDate']} to {campaign['EndDate'] or 'Ongoing'}"
        )

        with cols[2]:
            st.write("")  # Spacer
            if st.button(
                "➕ Add Lead",
                key=f"add_lead_{campaign['CampaignID']}",
                use_container_width=True,
            ):
                st.session_state.adding_lead_to_campaign_id = campaign["CampaignID"]
                st.rerun()

            action_cols = st.columns(2)
            if action_cols[0].button(
                "✏️", key=f"edit_camp_{campaign['CampaignID']}", help="Edit Campaign"
            ):
                st.session_state.editing_campaign_id = campaign["CampaignID"]
                st.rerun()
            if action_cols[1].button(
                "🗑️", key=f"del_camp_{campaign['CampaignID']}", help="Delete Campaign"
            ):
                execute_query(
                    "DELETE FROM campaigns WHERE CampaignID = %s",
                    (campaign["CampaignID"],),
                )
                st.success(f"Campaign '{campaign['Name']}' deleted.")
                st.rerun()

    def _render_campaign_form(self, campaign_id):
        """Renders the form for creating or editing a campaign."""
        is_edit = campaign_id != "new"
        title = "Edit Campaign" if is_edit else "Create New Campaign"
        campaign_data = (
            self.campaigns[self.campaigns["CampaignID"] == campaign_id].iloc[0]
            if is_edit
            else None
        )

        with st.form("campaign_form"):
            st.subheader(title)
            name = st.text_input(
                "Campaign Name*", value=campaign_data["Name"] if is_edit else ""
            )
            description = st.text_area(
                "Description", value=campaign_data["Description"] if is_edit else ""
            )

            c1, c2 = st.columns(2)
            start_date = c1.date_input(
                "Start Date",
                value=(
                    pd.to_datetime(campaign_data["StartDate"]).date()
                    if is_edit
                    else date.today()
                ),
            )
            end_date = c2.date_input(
                "End Date (optional)",
                value=(
                    pd.to_datetime(campaign_data["EndDate"]).date()
                    if is_edit and campaign_data["EndDate"]
                    else None
                ),
            )

            status = st.selectbox(
                "Status",
                ["Planned", "Active", "Completed", "Paused"],
                index=(
                    ["Planned", "Active", "Completed", "Paused"].index(
                        campaign_data["Status"]
                    )
                    if is_edit
                    else 0
                ),
            )

            submitted = st.form_submit_button("Save Campaign", type="primary")
            cancelled = st.form_submit_button("Cancel")

            if submitted:
                if not name:
                    st.error("Campaign Name is required.")
                else:
                    params = (name, description, start_date, end_date, status)
                    if is_edit:
                        query = "UPDATE campaigns SET Name=%s, Description=%s, StartDate=%s, EndDate=%s, Status=%s, UpdatedAt=NOW() WHERE CampaignID=%s"
                        params += (campaign_id,)
                    else:
                        query = "INSERT INTO campaigns (Name, Description, StartDate, EndDate, Status) VALUES (%s, %s, %s, %s, %s)"

                    if execute_query(query, params):
                        st.success(f"Campaign '{name}' saved successfully.")
                        st.session_state.editing_campaign_id = None
                        st.rerun()

            if cancelled:
                st.session_state.editing_campaign_id = None
                st.rerun()

    def _render_leads_tab(self):
        """Renders the UI for managing leads."""
        st.subheader("Manage Leads")
        # Add filters for leads if needed
        st.dataframe(
            self.leads,
            use_container_width=True,
            hide_index=True,
            column_config={
                "LeadID": "ID",
                "CampaignID": None,
                "CampaignName": "Campaign",
                "Name": "Lead Name",
                "Email": "Email Address",
                "Phone": "Phone Number",
                "Source": "Source",
                "Status": "Status",
                "CreatedAt": "Date Added",
            },
        )
        # Placeholder for individual lead actions
        selected_lead = st.selectbox(
            "Select a Lead to Log Interaction",
            self.leads["Name"].tolist() if not self.leads.empty else [],
        )
        if st.button("Log Interaction for Selected Lead"):
            if selected_lead:
                lead_id = self.leads[self.leads["Name"] == selected_lead][
                    "LeadID"
                ].iloc[0]
                st.session_state.logging_interaction_for_lead_id = lead_id
                st.rerun()

    def _render_lead_form(self, campaign_id):
        """Renders the form to add a new lead to a specific campaign."""
        campaign_name = self.campaigns[self.campaigns["CampaignID"] == campaign_id][
            "Name"
        ].iloc[0]
        with st.form("add_lead_form"):
            st.subheader(f"Add New Lead to Campaign: {campaign_name}")
            name = st.text_input("Lead Name*")
            c1, c2 = st.columns(2)
            email = c1.text_input("Email")
            phone = c2.text_input("Phone")
            source = st.selectbox("Source", ["Web", "Call", "Referral", "Other"])

            submitted = st.form_submit_button("Save Lead", type="primary")
            cancelled = st.form_submit_button("Cancel")

            if submitted:
                if not name:
                    st.error("Lead Name is required.")
                else:
                    query = "INSERT INTO leads (CampaignID, Name, Email, Phone, Source, Status) VALUES (%s, %s, %s, %s, %s, 'New')"
                    if execute_query(query, (campaign_id, name, email, phone, source)):
                        st.success(f"Lead '{name}' added successfully.")
                        st.session_state.adding_lead_to_campaign_id = None
                        st.rerun()
            if cancelled:
                st.session_state.adding_lead_to_campaign_id = None
                st.rerun()

    def _render_interactions_tab(self):
        """Renders the historical log of all interactions."""
        st.subheader("Interaction Logs")
        st.dataframe(
            self.interactions,
            use_container_width=True,
            hide_index=True,
            column_config={
                "InteractionID": "ID",
                "LeadID": None,
                "LeadName": "Lead Name",
                "Type": "Type",
                "Notes": "Notes",
                "Date": "Date",
                "Outcome": "Outcome",
            },
        )

    def _render_interaction_form(self, lead_id):
        """Renders the form to log a new interaction for a lead."""
        lead_name = self.leads[self.leads["LeadID"] == lead_id]["Name"].iloc[0]
        with st.form("log_interaction_form"):
            st.subheader(f"Log Interaction for: {lead_name}")
            interaction_type = st.selectbox(
                "Interaction Type", ["Call", "Email", "Meeting", "Other"]
            )
            outcome = st.selectbox("Outcome", ["Positive", "Neutral", "Negative"])
            notes = st.text_area("Notes*")

            new_lead_status = st.selectbox(
                "Update Lead Status (Optional)",
                ["(No Change)"] + self.leads["Status"].unique().tolist(),
            )

            submitted = st.form_submit_button("Log Interaction", type="primary")
            cancelled = st.form_submit_button("Cancel")

            if submitted:
                if not notes:
                    st.error("Notes are required for an interaction.")
                else:
                    # Log the interaction
                    query_interaction = "INSERT INTO interactions (LeadID, Type, Notes, Outcome) VALUES (%s, %s, %s, %s)"
                    execute_query(
                        query_interaction, (lead_id, interaction_type, notes, outcome)
                    )

                    # Update lead status if changed
                    if new_lead_status != "(No Change)":
                        query_status = "UPDATE leads SET Status = %s WHERE LeadID = %s"
                        execute_query(query_status, (new_lead_status, lead_id))

                    st.success(f"Interaction for '{lead_name}' logged.")
                    st.session_state.logging_interaction_for_lead_id = None
                    st.rerun()
            if cancelled:
                st.session_state.logging_interaction_for_lead_id = None
                st.rerun()
