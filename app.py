import streamlit as st
from supabase import create_client, Client
import pandas as pd

# Page configuration
st.set_page_config(page_title="Chit Fund Tracker", layout="wide")

# --- CUSTOMIZED MEMBERS LIST ---
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
        df_schedule, 
        column_config=schedule_config, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True, # <--- NEW: Hides the 0, 1, 2... numbering
        key="schedule_editor"
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

st.write("")
st.divider()

# --- MONTHLY DRILL-DOWN & MEMBER COLLECTIONS ---
st.header("🔍 Monthly Collections Drill-Down")

selected_month = st.selectbox("Select Month to view details:", options=range(1, 17), index=0)

month_data = df_schedule[df_schedule["month_no"] == selected_month]
if not month_data.empty:
    target_payout = month_data.iloc[0]["payout_amount"]
    recipient = month_data.iloc[0]["recipient_name"]
    st.info(f"**Target Payout for Month {selected_month}:** ₹{target_payout} | **Payout Recipient:** {recipient if pd.notna(recipient) else 'Not Assigned'}")

def load_monthly_collections(month):
    response = supabase.table("member_payments").select("*").eq("month_no", month).execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame({
            "id": [None] * 16,
            "month_no": [month] * 16,
            "member_name": MEMBERS,
            "amount": [6000] * 16,
            "status": ["Pending"] * 16
        })

df_collections = load_monthly_collections(selected_month)

# Sort Data Serially
df_collections['member_name'] = pd.Categorical(df_collections['member_name'], categories=MEMBERS, ordered=True)
df_collections = df_collections.sort_values('member_name').reset_index(drop=True)

collection_config = {
    "id": None, "created_at": None, "month_no": None, 
    "member_name": st.column_config.TextColumn("Member Name"),
    "amount": st.column_config.NumberColumn("Collection Amount", default=6000),
    "status": st.column_config.SelectboxColumn("Payment Status", options=["Pending", "Paid"], default="Pending")
}

st.write(f"### Collection Checklist - Month {selected_month}")
edited_collections = st.data_editor(
    df_collections, 
    column_config=collection_config, 
    disabled=["member_name"], 
    num_rows="fixed", 
    use_container_width=True, 
    hide_index=True, # <--- NEW: Hides the 0, 1, 2... numbering
    key=f"collections_editor_{selected_month}"
)

# --- CALCULATE MONTHLY TOTAL ---
paid_members = edited_collections[edited_collections["status"] == "Paid"]
monthly_total_collected = pd.to_numeric(paid_members["amount"], errors="coerce").fillna(0).sum()
monthly_target = 16 * 6000

st.metric(
    label=f"💰 Total Collected for Month {selected_month}", 
    value=f"₹{monthly_total_collected:,.0f}",
    delta=f"₹{monthly_target - monthly_total_collected:,.0f} remaining",
    delta_color="off"
)

st.write("")

# --- SAVE MONTHLY COLLECTIONS LOGIC ---
if st.button(f"💾 Save Collections for Month {selected_month}", type="secondary"):
    changes = st.session_state[f"collections_editor_{selected_month}"]
    try:
        if df_collections["id"].isnull().all():
            records_to_insert = edited_collections.drop(columns=["id"]).to_dict(orient="records")
            supabase.table("member_payments").insert(records_to_insert).execute()
        else:
            if changes.get("edited_rows"):
                for row_index, updates in changes["edited_rows"].items():
                    record_id = df_collections.iloc[row_index]["id"]
                    supabase.table("member_payments").update(updates).eq("id", record_id).execute()
                    
        st.success(f"Collections for Month {selected_month} saved securely!")
        st.rerun()
    except Exception as e:
        st.error(f"Error saving collections: {e}")
