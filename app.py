import streamlit as st
from supabase import create_client, Client
import pandas as pd

# Page configuration
st.set_page_config(page_title="Chit Fund Tracker", layout="wide")

# --- CUSTOMIZED MEMBERS LIST ---
# Numbered to ensure unique values for Streamlit dropdowns (prevents errors on duplicate names)
MEMBERS = [
    "1. Naveen", "2. hgh", "3. kjdf", "4. fss", 
    "5. jhf", "6. Naveenth", "7. hghgh", "8. kjdftt",
    "9. fssww", "10. jhf67", "11. Naveen", "12. hgh",
    "13. kjdf", "14. fss", "15. jhf", "16. erter"
]

st.title("Chit Fund Management Portal")

# 1. Initialize Supabase connection
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase secrets not found. Please check your .streamlit/secrets.toml or Streamlit Cloud Settings.")
        st.stop()

supabase = init_connection()

# 2. Fetch Master Schedule Data
def load_schedule_data():
    response = supabase.table("chit_fund_16_months").select("*").order("month_no").execute()
    if response.data:
        df = pd.DataFrame(response.data)
        if 'payout_date' in df.columns:
            # Convert string dates to datetime objects for Streamlit
            df['payout_date'] = pd.to_datetime(df['payout_date']).dt.date
        return df
    else:
        return pd.DataFrame(columns=["id", "month_no", "payout_date", "installment_amount", "payout_amount", "recipient_name", "status"])

df_schedule = load_schedule_data()

# --- MAIN SCHEDULE SECTION ---
with st.expander("📅 View/Edit 16-Month Master Schedule", expanded=False):
    schedule_config = {
        "id": None, "created_at": None,
        "month_no": st.column_config.NumberColumn("ಕ್ರಮ ಸಂಖ್ಯೆ (Month)", required=True, min_value=1),
        "payout_date": st.column_config.DateColumn("ದಿನಾಂಕ (Date)"),
        "installment_amount": st.column_config.NumberColumn("ಕಟ್ಟುವ ಹಣ (Installment)", default=6000),
        "payout_amount": st.column_config.TextColumn("ಕೊಡುವ ಹಣ (Payout Amount)"),
        "recipient_name": st.column_config.SelectboxColumn("ಸದಸ್ಯರ ಹೆಸರು (Recipient Name)", options=MEMBERS),
        "status": st.column_config.SelectboxColumn("ಸ್ಥಿತಿ (Status)", options=["Pending", "Paid"], default="Pending")
    }

    edited_schedule_df = st.data_editor(
        df_schedule, column_config=schedule_config, num_rows="dynamic", use_container_width=True, key="schedule_editor"
    )

    if st.button("💾 Save Master Schedule", type="primary"):
        changes = st.session_state["schedule_editor"]
        try:
            if changes.get("deleted_rows"):
                for row_index in changes["deleted_rows"]:
                    record_id = df_schedule.iloc[row_index]["id"]
                    supabase.table("chit_fund_16_months").delete().eq("id", record_id).execute()
            if changes.get("edited_rows"):
                for row_index, updates in changes["edited_rows"].items():
                    record_id = df_schedule.iloc[row_index]["id"]
                    if "payout_date" in updates and updates["payout_date"]:
                        updates["payout_date"] = updates["payout_date"].isoformat()
                    supabase.table("chit_fund_16_months").update(updates).eq("id", record_id).execute()
            if changes.get("added_rows"):
                for new_row in changes["added_rows"]:
                    if "payout_date" in new_row and new_row["payout_date"]:
                        new_row["payout_date"] = new_row["payout_date"].isoformat()
                    supabase.table("chit_fund_16_months").insert(new_row).execute()
            st.success("Master Schedule updated!")
            st.rerun()
        except Exception as e:
            st.error(f"Sync failed: {e}")

# --- FUND SUMMARY METRICS ---
st.subheader("📊 Fund Summary")
paid_df = edited_schedule_df[edited_schedule_df["status"] == "Paid"]
pending_df = edited_schedule_df[edited_schedule_df["status"] == "Pending"]

total_pool_per_month = 16 * 6000 
total_collected = len(paid_df) * total_pool_per_month
total_payout = pd.to_numeric(paid_df["payout_amount"], errors="coerce").fillna(0).sum()
remaining_balance = total_collected - total_payout

m1, m2, m3, m4 = st.columns(4)
m1.metric("Paid Months", f"{len(paid_df)} / 16")
m2.metric("Total Pool (Collected)", f"₹{total_collected:,.0f}")
m3.metric("Total Payouts", f"₹{total_payout:,.0f}")
m4.metric("Remaining Balance", f"₹{remaining_balance:,.0f}", delta_color="normal")
st.divider()

# --- MONTHLY DRILL-DOWN & MEMBER COLLECTIONS ---
st.header("🔍 Monthly Collections Drill-Down")

# Select a specific month
selected_month = st.selectbox("Select Month to view details:", options=range(1, 17), index=0)

# Show details for the selected month from the master schedule
month_data = df_schedule[df_schedule["month_no"] == selected_month]
if not month_data.empty:
    target_payout = month_data.iloc[0]["payout_amount"]
    recipient = month_data.iloc[0]["recipient_name"]
    st.info(f"**Target Payout for Month {selected_month}:** ₹{target_payout} | **Payout Recipient:** {recipient if pd.notna(recipient) else 'Not Assigned'}")

# Fetch member collection data for this specific month
def load_monthly_collections(month):
    response = supabase.table("member_payments").select("*").eq("month_no", month).order("id").execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        # If no data exists for this month in Supabase, auto-generate the 16 member slots locally
        return pd.DataFrame({
            "id": [None] * 16,
            "month_no": [month] * 16,
            "member_name": MEMBERS,
            "amount": [6000] * 16,
            "status": ["Pending"] * 16
        })

df_collections = load_monthly_collections(selected_month)

collection_config = {
    "id": None, "created_at": None, "month_no": None, # Hide backend IDs
    "member_name": st.column_config.SelectboxColumn("Member Name", options=MEMBERS, required=True),
    "amount": st.column_config.NumberColumn("Collection Amount", default=6000),
    "status": st.column_config.SelectboxColumn("Payment Status", options=["Pending", "Paid"], default="Pending")
}

st.write(f"### Collection Checklist - Month {selected_month}")
edited_collections = st.data_editor(
    df_collections, 
    column_config=collection_config, 
    num_rows="dynamic", 
    use_container_width=True, 
    key=f"collections_editor_{selected_month}"
)

# --- CALCULATE MONTHLY TOTAL ---
# 1. Filter the edited table to only show members who have paid
paid_members = edited_collections[edited_collections["status"] == "Paid"]

# 2. Sum the actual "amount" column for those paid members
monthly_total_collected = pd.to_numeric(paid_members["amount"], errors="coerce").fillna(0).sum()

# 3. Calculate the target amount (assuming 16 members at 6000 each)
monthly_target = 16 * 6000

# 4. Display the result prominently below the table
st.metric(
    label=f"💰 Total Collected for Month {selected_month}", 
    value=f"₹{monthly_total_collected:,.0f}",
    delta=f"₹{monthly_target - monthly_total_collected:,.0f} remaining",
    delta_color="off" # Keeps the remaining amount gray instead of red/green
)

st.write("") # Adds a tiny bit of vertical spacing

# --- SAVE MONTHLY COLLECTIONS LOGIC ---
if st.button(f"💾 Save Collections for Month {selected_month}", type="secondary"):
    changes = st.session_state[f"collections_editor_{selected_month}"]
    try:
        # If this is the first time saving for this month, insert all 16 rows to the database
        if df_collections["id"].isnull().all():
            records_to_insert = edited_collections.drop(columns=["id"]).to_dict(orient="records")
            supabase.table("member_payments").insert(records_to_insert).execute()
        else:
            # Handle Updates (Checking off a box)
            if changes.get("edited_rows"):
                for row_index, updates in changes["edited_rows"].items():
                    record_id = df_collections.iloc[row_index]["id"]
                    supabase.table("member_payments").update(updates).eq("id", record_id).execute()
            # Handle Deletions
            if changes.get("deleted_rows"):
                for row_index in changes["deleted_rows"]:
                    record_id = df_collections.iloc[row_index]["id"]
                    supabase.table("member_payments").delete().eq("id", record_id).execute()
            # Handle Additions (If you manually add a 17th row)
            if changes.get("added_rows"):
                for new_row in changes["added_rows"]:
                    new_row["month_no"] = selected_month
                    supabase.table("member_payments").insert(new_row).execute()
                    
        st.success(f"Collections for Month {selected_month} saved securely!")
        st.rerun()
    except Exception as e:
        st.error(f"Error saving collections: {e}")
