import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime, timedelta, time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Tail Risk", page_icon="📉", layout="wide")

st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(128, 128, 128, 0.1);
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stAlert {
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA FUNCTIONS ---

@st.cache_data
def process_csv_data(uploaded_file):
    if uploaded_file is None: return None, None
    try:
        df = pd.read_csv(uploaded_file)
        
        # Helper: Clean weird characters from scraping
        def clean(x): return str(x).replace('CET', '').replace('CEST', '').strip() if pd.notnull(x) else x
        
        # 1. Parse Dates
        df['Date_dt'] = pd.to_datetime(df['Date'], format='%d-%b-%y', errors='coerce')
        
        # Drop rows where Date failed to parse (Crashes the rest of the code)
        df = df.dropna(subset=['Date_dt'])
        
        # 2. Parse Times (Departure/Arrival)
        def parse_time(row, col):
            try:
                t_str = clean(row[col])
                dt_str = f"{row['Date_dt'].strftime('%Y-%m-%d')} {t_str}"
                return pd.to_datetime(dt_str, format='%Y-%m-%d %I:%M%p')
            except:
                return pd.NaT

        df['actual_out'] = df.apply(lambda r: parse_time(r, 'Departure'), axis=1)
        df['actual_in'] = df.apply(lambda r: parse_time(r, 'Arrival'), axis=1)

        # 3. Handle Cancellations
        if 'Duration' in df.columns:
            df['is_cancelled'] = df['Duration'].astype(str).str.contains('Cancelled', case=False)
        else:
            df['is_cancelled'] = False

        # 4. Handle Overnight (Arrival < Departure)
        mask_valid = pd.notnull(df['actual_in']) & pd.notnull(df['actual_out'])
        mask_overnight = (df.loc[mask_valid, 'actual_in'].dt.time < df.loc[mask_valid, 'actual_out'].dt.time)
        df.loc[mask_valid & mask_overnight, 'actual_in'] += timedelta(days=1)

        # 5. Metadata Extraction
        meta = {
            "origin": df['Origin'].mode()[0] if 'Origin' in df.columns else "?",
            "dest": df['Destination'].mode()[0] if 'Destination' in df.columns else "?",
            "aircraft": df['Aircraft'].mode()[0] if 'Aircraft' in df.columns else "Unknown",
            "count": len(df)
        }
        df['source_type'] = 'csv'
        return df, meta

    except Exception as e:
        return None, f"Error processing CSV: {str(e)}"

@st.cache_data(ttl=3600, show_spinner="Fetching comprehensive history...")
def fetch_live_history(ident, api_key):
    if not api_key: return None, "No API Key."
    
    url = f"https://aeroapi.flightaware.com/aeroapi/flights/{ident}"
    headers = {"x-apikey": api_key}
    params = {"max_pages": 3} 

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200: return None, f"API Error {response.status_code}"
        
        data = response.json()
        flights = data.get('flights', [])
        if not flights: return None, "No history."

        processed = []
        for f in flights:
            dest_tz = f.get('destination', {}).get('timezone', 'UTC')
            
            utc_in = f.get('actual_in') or f.get('estimated_in')
            sched_in = f.get('scheduled_in')
            
            row = {
                'origin': f.get('origin', {}).get('code'),
                'dest': f.get('destination', {}).get('code'),
                'aircraft': f.get('aircraft_type'),
                'is_cancelled': 'Cancelled' in f.get('status', ''),
                'source_type': 'api'
            }
            
            if utc_in and sched_in:
                ts_in = pd.to_datetime(utc_in, utc=True)
                ts_sched = pd.to_datetime(sched_in, utc=True)
                
                row['actual_in_local'] = ts_in.tz_convert(dest_tz).tz_localize(None)
                row['sched_in_local'] = ts_sched.tz_convert(dest_tz).tz_localize(None)
                row['Date_dt'] = row['sched_in_local']
                
                row['delay_minutes'] = (row['actual_in_local'] - row['sched_in_local']).total_seconds() / 60
            else:
                row['Date_dt'] = pd.to_datetime(f.get('scheduled_out')).tz_localize(None)
                row['delay_minutes'] = np.nan 
            
            processed.append(row)
            
        df = pd.DataFrame(processed)
        meta = {
            "origin": df['origin'].mode()[0] if not df.empty else "?",
            "dest": df['dest'].mode()[0] if not df.empty else "?",
            "aircraft": df['aircraft'].mode()[0] if not df.empty else "?",
            "count": len(df)
        }
        return df, meta

    except Exception as e:
        return None, f"API Error: {str(e)}"

# --- 3. MAIN APP ---

st.title("Tail Risk 📉")
st.markdown("### The Probabilistic Flight Planner")

# --- SIDEBAR (Per User's request) ---
with st.sidebar:
    st.header("1. The Data")
    data_mode = st.radio("Input:", ["FlightAware API", "Upload CSV"])
    
    st.markdown("---")
    
    st.header("2. The Schedule")
    st.info("💡 **Split Schedule Smart-Filter:** We use your time to find relevant historical flights (e.g., ignoring morning flights if you fly in the evening).")
    
    sched_arr = st.time_input("Scheduled Arrival", value=time(16, 45), step=60)
    
    st.markdown("---")
    
    st.header("3. The Deadline")
    has_deadline = st.checkbox("Got Someplace to be?", value=True)
    if has_deadline:
        deadline_time = st.time_input("Cutoff Time", value=time(18, 00), step=60)

# --- LOAD DATA ---
df = None
meta = {}

if data_mode == "FlightAware API":
    ident = st.text_input("Flight Number", value="VY6612")
    if st.button("Fetch History", type="primary"):
        api_key = st.secrets.get("FLIGHTAWARE_API_KEY")
        df, meta = fetch_live_history(ident, api_key)
        if df is None: st.error(meta)

elif data_mode == "Upload CSV":
    # --- TUTORIAL SECTION ---
    with st.expander("📝 Tutorial: How to get your 3-month CSV"):
        st.markdown("For deep statistical analysis, we need more history than the API provides for free.")
        st.markdown("**Required Columns:** `Date`, `Departure`, `Arrival`. **Optional:** `Aircraft`.")
        
        # INSERT VIDEO EMBED HERE:
        # Use the public URL from Loom, YouTube, or Vimeo
        st.video("https://cdn.loom.com/sessions/thumbnails/45396d34f5bf46fa963b98b47f993a7e-30574d646793ab7d.mp4")
        
        example_data = {
            "Date": ["21-Nov-25", "20-Nov-25"],
            "Aircraft": ["A320", "A20N"],
            "Departure": ["07:17AM CET", "06:56AM CET"],
            "Arrival": ["08:34AM CET", "08:08AM CET"]
        }
        st.table(pd.DataFrame(example_data))

    uploaded = st.file_uploader("Upload CSV", type=['csv'])
    if uploaded:
        df, meta = process_csv_data(uploaded)
        if df is None: st.error(meta)

# --- ANALYSIS ENGINE (Starts here - assumes df is populated) ---

if df is not None:
    st.divider()
    
    # 1. STANDARDIZE DELAY METRICS
    if df['source_type'].iloc[0] == 'csv':
        
        # KEY FIX: Ensure datetime conversion is safe for CSVs
        def combine_sched(r):
            if pd.isna(r['Date_dt']): return pd.NaT
            try:
                return datetime.combine(r['Date_dt'].date(), sched_arr)
            except:
                return pd.NaT

        user_sched_series = df.apply(combine_sched, axis=1)
        
        df['user_sched_dt'] = pd.to_datetime(user_sched_series, errors='coerce')
        df = df.dropna(subset=['user_sched_dt'])
        
        df['delay_minutes'] = (df['actual_in'] - df['user_sched_dt']).dt.total_seconds() / 60
        
        # Fix 24h wrap
        df.loc[df['delay_minutes'] < -720, 'delay_minutes'] += 1440
        df.loc[df['delay_minutes'] > 720, 'delay_minutes'] -= 1440
        
        # FIX FOR SMART FILTER: Use Actual Arrival Time as the filter base
        df['sched_in_local'] = df['actual_in']
    
    # 2. INTELLIGENT FILTERING
    user_mins = sched_arr.hour * 60 + sched_arr.minute
    
    def is_relevant_time(row_sched_dt):
        if pd.isna(row_sched_dt): return True 
        row_mins = row_sched_dt.hour * 60 + row_sched_dt.minute
        diff = abs(row_mins - user_mins)
        if diff > 720: diff = 1440 - diff
        return diff <= 180 # 3 Hour Window

    # The filter base is now dynamic: actual_in for CSV, scheduled_in for API
    df['is_relevant'] = df['sched_in_local'].apply(is_relevant_time)
    relevant_df = df[df['is_relevant']].copy()
    hidden_count = len(df) - len(relevant_df)
    
    if hidden_count > 0:
        st.info(f"🔎 **Smart Filter Active:** Analyzed {len(df)} flights. Hidden {hidden_count} due to schedule mismatch.")
    
    # 3. METRICS
    cancel_count = relevant_df['is_cancelled'].sum()
    total_relevant = len(relevant_df)
    cancel_rate = cancel_count / total_relevant if total_relevant > 0 else 0
    
    valid_df = relevant_df[~relevant_df['is_cancelled']].dropna(subset=['delay_minutes'])
    
    avg_delay = valid_df['delay_minutes'].mean() if not valid_df.empty else 0
    severe_count = len(valid_df[valid_df['delay_minutes'] > 45])
    
    prob_miss_text = "N/A"
    is_high_risk = False
    
    if has_deadline:
        today = datetime.now().date()
        dt_deadline = datetime.combine(today, deadline_time)
        dt_sched = datetime.combine(today, sched_arr)
        
        buffer_mins = (dt_deadline - dt_sched).total_seconds() / 60
        if buffer_mins < -720: buffer_mins += 1440
        
        miss_count = len(valid_df[valid_df['delay_minutes'] > buffer_mins]) + cancel_count
        prob_miss = miss_count / total_relevant if total_relevant > 0 else 0
        prob_miss_text = f"{prob_miss:.1%}"
        is_high_risk = prob_miss > 0.15

    # --- DISPLAY ---
    st.subheader(f"Analysis: {meta['origin']} ➝ {meta['dest']}")
    st.caption(f"Based on {total_relevant} flights. Aircraft: **{meta['aircraft']}**")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg Delay", f"{avg_delay:+.0f} min", delta="Late" if avg_delay > 15 else "On Time", delta_color="inverse")
    c2.metric("Significant Delays (>45m)", f"{severe_count}", delta="High" if severe_count > 5 else "Low", delta_color="inverse")
    c3.metric("Cancellation Rate", f"{cancel_rate:.1%}", delta="Warning" if cancel_rate > 0.02 else "Normal", delta_color="inverse")
    if has_deadline:
        c4.metric(f"Miss Probability", prob_miss_text, delta="-High Risk" if is_high_risk else "Safe", delta_color="inverse")

    st.divider()

    # --- PLOT ---
    def get_category(row):
        delay = row['delay_minutes']
        if has_deadline and delay > buffer_mins: return "Missed Deadline"
        if delay > 45: return "Significant (>45m)"
        if delay > 15: return "Nuisance (15-45m)"
        return "On Time / Early (<15m)"

    valid_df['Risk Category'] = valid_df.apply(get_category, axis=1)
    
    color_map = {
        "On Time / Early (<15m)": "#2ecc71",
        "Nuisance (15-45m)": "#f1c40f",
        "Significant (>45m)": "#e67e22",
        "Missed Deadline": "#e74c3c"
    }

    fig = px.histogram(
        valid_df, x="delay_minutes", color="Risk Category", 
        color_discrete_map=color_map, nbins=25,
        title=f"Delay Distribution for {sched_arr.strftime('%I:%M %p')} Schedule",
        labels={'delay_minutes': 'Delay vs Schedule (Minutes)'}
    )
    if has_deadline:
        fig.add_vline(x=buffer_mins, line_dash="dash", line_color="white", annotation_text="DEADLINE")
    
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("See Underlying Data"):
        st.dataframe(valid_df[['Date_dt', 'delay_minutes', 'Risk Category']].sort_values('Date_dt', ascending=False))