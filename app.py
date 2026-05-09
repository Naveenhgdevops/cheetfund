import streamlit as st
from supabase import create_client, Client
import pandas as pd

# Page configuration
st.set_page_config(page_title="Chit Fund Tracker", layout="wide")
st.title("Chit Fund Management Portal")

# 1. Initialize Supabase connection
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase secrets not found. Please check your .streamlit/secrets.toml or Streamlit Cloud Secrets.")
        st.stop()

supabase = init_connection()

# 2. Fetch data from Supabase with Date Fix
def load_data():
    response = supabase.table("chit_fund_16_months").select("*").order("month_no").execute()
    if response.data:
        df = pd.DataFrame(response.data)
        
        # FIX: Convert the string date from Supabase to a proper Date object for Streamlit
        if 'payout_date' in df.columns:
            df['payout_date'] = pd.to_datetime(df['payout_date']).dt.date
            
        return df
    else:
        # Return empty template if no data exists
        return pd.DataFrame(columns=["id", "month_no", "payout_date", "installment_amount", "payout_amount", "recipient_name", "status"])

df = load_data()

st.subheader("📅 16-Month Schedule")

# 3. Column Configuration (Kannada Headers & Editor Logic)
column_config = {
    "id": None, # Hide internal UUID
    "created_at": None, # Hide timestamp
    "month_no": st.column_config.NumberColumn("ಕ್ರಮ ಸಂಖ್ಯೆ (Month)", required=True, min_value=1),
    "payout_date": st.column_config.DateColumn("ದಿನಾಂಕ (Date)"),
    "installment_amount": st.column_config.NumberColumn("ಕಟ್ಟುವ ಹಣ (Installment)", default=6000),
    "payout_amount": st.column_config.TextColumn("ಕೊಡುವ ಹಣ (Payout Amount)"),
    "recipient_name": st.column_config.TextColumn("ಸದಸ್ಯರ ಹೆಸರು (Recipient Name)"),
    "status": st.column_config.SelectboxColumn("ಸ್ಥಿತಿ (Status)", options=["Pending", "Paid"], default="Pending")
}

# 4. The Interactive Data Editor
edited_df = st.data_editor(
    df,
    column_config=column_config,
    num_rows="dynamic", # Allows you to add or delete months
    use_container_width=True,
    key="data_editor"
)

# 5. 📊 Dynamic Fund Summary (Calculates instantly as you type)
st.divider()
st.subheader("📊 Fund Summary")

# Filter logic for metrics
paid_df = edited_df[edited_df["status"] == "Paid"]
pending_df = edited_df[edited_df["status"] == "Pending"]

# Calculations (Assuming 16 members @ 6000 each)
total_pool_per_month = 16 * 6000 
total_collected = len(paid_df) * total_pool_per_month

# Convert Payouts to numbers (safely ignores "ಕಮಿಷನ್ ಚೀಟಿ" text)
total_payout = pd.to_numeric(paid_df["payout_amount"], errors="coerce").fillna(0).sum()

# Remaining balance in the hand
remaining_balance = total_collected - total_payout

# Layout for Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Paid Months", f"{len(paid_df)} / 16")
m2.metric("Total Pool (Collected)", f"₹{total_collected:,.0f}")
m3.metric("Total Payouts", f"₹{total_payout:,.0f}")
m4.metric("Remaining Balance", f"₹{remaining_balance:,.0f}", delta_color="normal")

st.info(f"💡 Future expected collections: ₹{(len(pending_df) * total_pool_per_month):,.0f}")
st.divider()

# 6. Database Saving Logic
if st.button("💾 Save All Changes to Database", type="primary"):
    changes = st.session_state["data_editor"]
    
    try:
        # Handle Deletions
        if changes.get("deleted_rows"):
            for row_index in changes["deleted_rows"]:
                record_id = df.iloc[row_index]["id"]
                supabase.table("chit_fund_16_months").delete().eq("id", record_id).execute()
        
        # Handle Updates (Editing existing cells)
        if changes.get("edited_rows"):
            for row_index, updates in changes["edited_rows"].items():
                record_id = df.iloc[row_index]["id"]
                # If date was updated, convert it to string for Supabase
                if "payout_date" in updates and updates["payout_date"]:
                    updates["payout_date"] = updates["payout_date"].isoformat()
                supabase.table("chit_fund_16_months").update(updates).eq("id", record_id).execute()
                
        # Handle Additions (New rows)
        if changes.get("added_rows"):
            for new_row in changes["added_rows"]:
                if "payout_date" in new_row and new_row["payout_date"]:
                    new_row["payout_date"] = new_row["payout_date"].isoformat()
                supabase.table("chit_fund_16_months").insert(new_row).execute()
                
        st.success("Successfully synced with Supabase!")
        st.rerun() # Refresh to show clean data
        
    except Exception as e:
        st.error(f"Sync failed: {e}")
