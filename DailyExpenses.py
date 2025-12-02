import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import calendar
import altair as alt

# -----------------------
# 1. PAGE CONFIGURATION
# -----------------------
st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# -----------------------
# 2. LOGIN SYSTEM
# -----------------------
def check_password():
    """Returns `True` if the user had the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["login"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password
        else:
            st.session_state["password_correct"] = False

    # Initialize session state for password_correct
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Show input if not logged in
    if not st.session_state["password_correct"]:
        st.text_input(
            "🔒 Please enter your password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        if "password_correct" in st.session_state and st.session_state["password_correct"] is False:
            st.error("😕 Password incorrect")
        return False
    else:
        return True

if not check_password():
    st.stop()  # STOPS THE APP HERE if not logged in

# =========================================================
#  🎉 LOGGED IN! THE REST OF YOUR APP STARTS BELOW
# =========================================================

# -----------------------
# 3. CONFIGURATION & SETUP
# -----------------------
SPREADSHEET_NAME = "DailyExpenses"

# Categories List
CATEGORIES = [
    "Groceries", "Outside Food", "Lunch", "Snacks", "Petrol", 
    "Trip", "Phone", "Bike", "Medical", 
    "Rent", "House", "Personal", "Others", "TV/Subscriptions", "Gifts"
]

# -----------------------
# 4. DATA LOADING (CLOUD READY)
# -----------------------
@st.cache_resource
def get_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    else:
        st.error("🚨 Secrets not found! Please check Streamlit Cloud settings.")
        st.stop()

def get_data():
    client = get_client()
    try:
        sh = client.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        st.error(f"❌ Spreadsheet '{SPREADSHEET_NAME}' not found.")
        st.stop()
    
    # 1. Expenses
    sheet_exp = sh.sheet1
    df_exp = pd.DataFrame(sheet_exp.get_all_records())
    if not df_exp.empty:
        df_exp["Date"] = pd.to_datetime(df_exp["Date"], errors="coerce")
        df_exp["Amount"] = pd.to_numeric(df_exp["Amount"], errors="coerce").fillna(0.0)
        df_exp = df_exp.dropna(subset=["Date"])

    # 2. Income
    try:
        sheet_inc = sh.worksheet("Income")
    except:
        sheet_inc = sh.add_worksheet(title="Income", rows="100", cols="4")
        sheet_inc.append_row(["Month_Year", "Amount", "Source", "Date_Added"])
    df_inc = pd.DataFrame(sheet_inc.get_all_records())

    # 3. Category Budgets
    try:
        sheet_cat_bud = sh.worksheet("CategoryBudgets")
    except:
        sheet_cat_bud = sh.add_worksheet(title="CategoryBudgets", rows="200", cols="4")
        sheet_cat_bud.append_row(["Month_Year", "Category", "Planned_Amount", "Date_Added"])
    df_cat_bud = pd.DataFrame(sheet_cat_bud.get_all_records())
    
    return sheet_exp, sheet_inc, sheet_cat_bud, df_exp, df_inc, df_cat_bud

try:
    sheet_exp, sheet_inc, sheet_cat_bud, df_exp, df_inc, df_cat_bud = get_data()
except Exception as e:
    st.error(f"Error connecting to Google Sheets: {e}")
    st.stop()

# -----------------------
# 5. SMART NOTIFICATION (Day 25 Logic)
# -----------------------
today = datetime.now()
curr_month_str = today.strftime("%Y-%m")

if today.month == 12:
    next_month_str = f"{today.year + 1}-01"
else:
    next_month_str = f"{today.year}-{today.month + 1:02d}"

if today.day >= 25:
    target_plan_month = next_month_str
    prompt_msg = f"📅 Upcoming: Plan Income for {next_month_str}"
else:
    target_plan_month = curr_month_str
    prompt_msg = f"⚠️ Action: Set Income for {curr_month_str}"

income_exists = False
if not df_inc.empty:
    match = df_inc[df_inc["Month_Year"] == target_plan_month]
    if not match.empty:
        income_exists = True

if not income_exists and not st.session_state.get('skip_prompt', False):
    with st.expander(prompt_msg, expanded=True):
        st.write("Start your budget by setting your expected Income/Salary.")
        with st.form("quick_salary"):
            sal_in = st.number_input(f"Salary for {target_plan_month}", min_value=0.0, step=1000.0)
            if st.form_submit_button("✅ Set Salary"):
                sheet_inc.append_row([target_plan_month, sal_in, "Salary", today.strftime("%Y-%m-%d")])
                st.success("Salary Set! Please refresh.")
                st.cache_data.clear()
                st.rerun()
        if st.button("❌ Skip"):
            st.session_state['skip_prompt'] = True
            st.rerun()

# -----------------------
# 6. MAIN LAYOUT
# -----------------------
st.title("💰 Smart Finance Tracker")
if st.button("🔒 Logout"):
    st.session_state["password_correct"] = False
    st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["💸 Add Daily Expense", "📊 Dashboard", "📅 Analysis", "📝 Budget Planner"])

# ==========================================
# TAB 1: ADD EXPENSE
# ==========================================
with tab1:
    st.subheader("Log Transaction")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1: date_input = st.date_input("Date", datetime.now())
        with c2: category = st.selectbox("Category", CATEGORIES)
        
        desc = st.text_input("Description")
        amt = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
        
        if st.form_submit_button("➕ Save Expense"):
            row = [date_input.strftime("%Y-%m-%d"), category, desc, float(amt)]
            sheet_exp.append_row(row)
            st.success("Saved!")
            st.cache_data.clear()

# ==========================================
# TAB 2: DASHBOARD
# ==========================================
with tab2:
    if df_exp.empty:
        st.info("No expenses yet.")
    else:
        dash_df = df_exp[(df_exp["Date"].dt.month == today.month) & (df_exp["Date"].dt.year == today.year)]
        
        curr_sal = 0.0
        if not df_inc.empty:
            m = df_inc[df_inc["Month_Year"] == curr_month_str]
            if not m.empty: curr_sal = float(m.iloc[-1]["Amount"])

        curr_plan = pd.DataFrame()
        if not df_cat_bud.empty:
            raw_plan = df_cat_bud[df_cat_bud["Month_Year"] == curr_month_str]
            curr_plan = raw_plan.groupby("Category")["Planned_Amount"].sum().reset_index()

        total_spent = dash_df["Amount"].sum()
        total_planned = curr_plan["Planned_Amount"].sum() if not curr_plan.empty else 0
        
        days_passed = today.day
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        projected = (total_spent / days_passed) * days_in_month if days_passed > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💵 Income", f"₹{curr_sal:,.0f}")
        k2.metric("📉 Planned Budget", f"₹{total_planned:,.0f}")
        k3.metric("💸 Actual Spent", f"₹{total_spent:,.0f}")
        k4.metric("🔮 Projected End", f"₹{projected:,.0f}", delta=f"{projected-total_planned:,.0f} vs Plan", delta_color="inverse")

        st.divider()

        col_chart, col_data = st.columns([2, 1])
        
        with col_chart:
            st.subheader("📊 Plan vs Reality")
            actual_grp = dash_df.groupby("Category")["Amount"].sum().reset_index()
            
            if not curr_plan.empty:
                merged = pd.merge(curr_plan, actual_grp, on="Category", how="outer").fillna(0)
                merged.columns = ["Category", "Planned", "Actual"]
            else:
                merged = actual_grp.rename(columns={"Amount": "Actual"})
                merged["Planned"] = 0
            
            merged["Is_Over_Budget"] = merged["Actual"] > merged["Planned"]
            melted = merged.melt(id_vars=["Category", "Is_Over_Budget"], value_vars=["Planned", "Actual"], var_name="Type", value_name="Amount")
            
            def get_bar_color(row):
                if row["Type"] == "Planned": return "#e0e0e0" 
                elif row["Is_Over_Budget"]: return "#ff4b4b" 
                else: return "#2ca02c" 

            melted["Color"] = melted.apply(get_bar_color, axis=1)

            chart = alt.Chart(melted).mark_bar().encode(
                x=alt.X('Category:N', sort='-y'),
                y='Amount:Q',
                xOffset='Type:N',
                color=alt.Color('Color', scale=None, legend=None), 
                tooltip=['Category', 'Type', 'Amount']
            ).properties(height=350)
            
            st.altair_chart(chart, use_container_width=True)

        with col_data:
            st.subheader("⚠️ Over Limit")
            merged["Diff"] = merged["Planned"] - merged["Actual"]
            over_budget = merged[merged["Diff"] < 0].copy()
            over_budget["Over By"] = over_budget["Diff"].abs()
            
            if not over_budget.empty:
                st.dataframe(
                    over_budget[["Category", "Over By"]].style.format({"Over By": "₹{:.0f}"}), 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.success("All Good!")

        st.subheader("📈 Daily Trend")
        daily = dash_df.groupby("Date")["Amount"].sum().reset_index()
        st.line_chart(daily.set_index("Date"))

# ==========================================
# TAB 3: ANALYSIS
# ==========================================
with tab3:
    if df_exp.empty:
        st.write("No data.")
    else:
        st.subheader("📅 Weekly Operating Expenses")
        st.caption("Excludes Rent, House, TV, Gifts")
        
        excluded_cats = ["Rent", "House", "TV/Subscriptions", "Gifts"]
        weekly_df = df_exp[~df_exp["Category"].isin(excluded_cats)].copy()
        
        if not weekly_df.empty:
            weekly_chart = alt.Chart(weekly_df).mark_bar().encode(
                x=alt.X('yearweek(Date):O', title="Week"), 
                y=alt.Y('sum(Amount):Q', title="Total Spent"),
                color=alt.Color('Category:N'),
                tooltip=['yearweek(Date):O', 'Category', 'sum(Amount):Q']
            ).properties(height=400)
            
            st.altair_chart(weekly_chart, use_container_width=True)
        else:
            st.info("No variable expenses found.")
        
        st.divider()

        st.subheader("🆚 History: This Month vs Last Month")
        
        first_day_curr = today.replace(day=1)
        last_month_date = first_day_curr - timedelta(days=1)
        prev_month_idx = last_month_date.month
        
        curr_df = df_exp[(df_exp["Date"].dt.month == today.month) & (df_exp["Date"].dt.year == today.year)]
        prev_df = df_exp[(df_exp["Date"].dt.month == prev_month_idx)]
        
        c_total = curr_df["Amount"].sum()
        p_total = prev_df["Amount"].sum()
        
        st.metric("Total Spending Delta", f"₹{c_total:,.0f}", delta=f"{c_total - p_total:,.0f} vs Last Month", delta_color="inverse")
        
        c_cat = curr_df.groupby("Category")["Amount"].sum().reset_index().rename(columns={"Amount": "Current"})
        p_cat = prev_df.groupby("Category")["Amount"].sum().reset_index().rename(columns={"Amount": "Previous"})
        
        comp_merged = pd.merge(c_cat, p_cat, on="Category", how="outer").fillna(0)
        comp_melt = comp_merged.melt("Category", var_name="Period", value_name="Amount")
        
        chart_hist = alt.Chart(comp_melt).mark_bar().encode(
            x=alt.X('Category:N'),
            y='Amount:Q',
            color=alt.Color('Period:N', scale=alt.Scale(range=['#1f77b4', '#aec7e8'])),
            tooltip=['Category', 'Period', 'Amount']
        ).properties(height=400)
        
        st.altair_chart(chart_hist, use_container_width=True)

# ==========================================
# TAB 4: BUDGET PLANNER
# ==========================================
with tab4:
    plan_month_opt = st.radio("Select Month to Plan:", [curr_month_str, next_month_str], horizontal=True)
    col_left, col_right = st.columns([1, 1.5])

    with col_left:
        current_salary = 0.0
        if not df_inc.empty:
            m = df_inc[df_inc["Month_Year"] == plan_month_opt]
            if not m.empty: current_salary = float(m.iloc[-1]["Amount"])
            
        with st.form("salary_update"):
            st.write(f"**Income for {plan_month_opt}**")
            new_salary = st.number_input("Amount", value=current_salary, step=1000.0)
            if st.form_submit_button("Update Income"):
                sheet_inc.append_row([plan_month_opt, new_salary, "Salary", today.strftime("%Y-%m-%d")])
                st.success("Updated")
                st.cache_data.clear()
                st.rerun()
        
        st.divider()
        
        st.write(f"**Add Expense Budget ({plan_month_opt})**")
        with st.form("add_cat_budget"):
            c_cat, c_amt = st.columns([2, 1])
            with c_cat: cat_input = st.selectbox("Category", CATEGORIES)
            with c_amt: amt_input = st.number_input("Limit", min_value=0.0, step=100.0)
            
            if st.form_submit_button("Add Allocation"):
                if amt_input > 0:
                    sheet_cat_bud.append_row([plan_month_opt, cat_input, amt_input, today.strftime("%Y-%m-%d")])
                    st.success(f"Added {cat_input}")
                    st.cache_data.clear()
                    st.rerun()

    with col_right:
        st.write("### 📋 Budget Plan")
        plan_df = pd.DataFrame()
        if not df_cat_bud.empty:
            plan_df = df_cat_bud[df_cat_bud["Month_Year"] == plan_month_opt]

        total_alloc = 0.0
        if not plan_df.empty:
            display_df = plan_df.groupby("Category")["Planned_Amount"].sum().reset_index()
            total_alloc = display_df["Planned_Amount"].sum()
            balance = new_salary - total_alloc
            
            m1, m2 = st.columns(2)
            m1.metric("Total Income", f"₹{new_salary:,.0f}")
            m2.metric("Remaining to Allocate", f"₹{balance:,.0f}", delta_color="normal" if balance >= 0 else "inverse")

            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No categories allocated yet.")
