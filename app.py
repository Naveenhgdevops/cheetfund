import streamlit as st
from supabase import create_client, Client
import pandas as pd

st.set_page_config(page_title="Chit Fund Tracker", layout="wide")
st.title("Chit Fund Management Portal")

# Initialize Supabase connection
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

# Fetch data from Supabase
def load_data():
    response = supabase.table("chit_fund_16_months").select("*").order("month_no").execute()
    if response.data:
        return pd.DataFrame(response.data)
    else:
        return pd.DataFrame(columns=["id", "month_no", "payout_date", "installment_amount", "payout_amount", "recipient_name", "status"])

df = load_data()

st.subheader("16-Month Schedule")

# Configure the columns to match Kannada headers and data types
column_config = {
    "id": None, # Hide the UUID column from the UI
    "created_at": None,
    "month_no": st.column_config.NumberColumn("ಕ್ರಮ ಸಂಖ್ಯೆ (Month)", required=True, min_value=1),
    "payout_date": st.column_config.DateColumn("ದಿನಾಂಕ (Date)"),
    "installment_amount": st.column_config.NumberColumn("ಕಟ್ಟುವ ಹಣ (Installment)", default=6000),
    "payout_amount": st.column_config.TextColumn("ಕೊಡುವ ಹಣ (Payout Amount)"),
    "recipient_name": st.column_config.TextColumn("ಸದಸ್ಯರ ಹೆಸರು (Recipient Name)"),
    "status": st.column_config.SelectboxColumn("ಸ್ಥಿತಿ (Status)", options=["Pending", "Paid"], default="Pending")
}

# Display the interactive data editor
edited_df = st.data_editor(
    df,
    column_config=column_config,
    num_rows="dynamic", # Allows adding and deleting rows
    use_container_width=True,
    key="data_editor"
)

# --- FUND SUMMARY METRICS ---
st.divider()
st.subheader("📊 Fund Summary")

# 1. Filter rows based on their status
paid_df = edited_df[edited_df["status"] == "Paid"]
pending_df = edited_df[edited_df["status"] == "Pending"]

# 2. Calculations
total_pool_per_month = 16 * 6000 
total_collected = len(paid_df) * total_pool_per_month

# Convert payout amounts to numbers (safely ignores text like "ಕಮಿಷನ್ ಚೀಟಿ" and treats it as 0)
total_payout = pd.to_numeric(paid_df["payout_amount"], errors="coerce").fillna(0).sum()

# Remaining amount (Total collected minus what was paid out)
remaining_balance = total_collected - total_payout

# Total amount left to be collected in the future
pending_collection = len(pending_df) * total_pool_per_month

# 3. Display Metrics in a neat row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Paid Months", f"{len(paid_df)} / 16")
col2.metric("Total Pool Collected", f"₹ {total_collected:,.0f}")
col3.metric("Total Payouts", f"₹ {total_payout:,.0f}")
col4.metric("Remaining Balance", f"₹ {remaining_balance:,.0f}")

st.write(f"*Total pending collections remaining for the fund: ₹ {pending_collection:,.0f}*")
st.divider()

# --- DATABASE SAVING LOGIC ---
if st.button("Save Changes to Database", type="primary"):
    # Streamlit stores edited/added/deleted data in session state
    changes = st.session_state["data_editor"]
    
    try:
        # 1. Handle Deletions
        if changes.get("deleted_rows"):
            for row_index in changes["deleted_rows"]:
                record_id = df.iloc[row_index]["id"]
                supabase.table("chit_fund_16_months").delete().eq("id", record_id).execute()
        
        # 2. Handle Updates
        if changes.get("edited_rows"):
            for row_index, updates in changes["edited_rows"].items():
                record_id = df.iloc[row_index]["id"]
                # Convert the updates dict to match Supabase schema
                supabase.table("chit_fund_16_months").update(updates).eq("id", record_id).execute()
                
        # 3. Handle Additions
        if changes.get("added_rows"):
            for new_row in changes["added_rows"]:
                supabase.table("chit_fund_16_months").insert(new_row).execute()
                
        st.success("Database updated successfully!")
        st.rerun() # Refresh the app to pull fresh data
        
    except Exception as e:
        st.error(f"An error occurred: {e}")
