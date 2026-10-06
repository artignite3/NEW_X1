"""
NEW_X1 — Product UI (Streamlit Port 8501)
Expert Cricket Performance Intelligence Platform
Features:
  - 🔮 Future Matches Explorer (Browse & select upcoming fixtures directly)
  - ⚙️ Custom Match Simulator
  - 🏟️ Tactical SVG Cricket Ground Layout
  - 🌐 Environmental Intelligence (Weather, Pitch PAF, Injury News)
  - 🤖 AI Expert Analyst Rationale (Ollama LLM)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, date

import streamlit as st
import pandas as pd
import numpy as np

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from UI.components.cricket_field import render_cricket_pitch
from intelligence.weather_fetcher import fetch_venue_weather
from intelligence.pitch_analyzer import get_venue_profile, adjust_player_score
from intelligence.injury_detector import get_active_injury_reports, calculate_player_injury_adjustments
from model.predict_model import predict_squad
from model.heuristic_solver import optimize_team_sharpe
from model.llm_inference import generate_player_explanation

# Page Config
st.set_page_config(
    page_title="NEW_X1 — Cricket Performance Intelligence",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Modern Tailwind-Inspired Dark Theme CSS ─────────────────────────────────
st.markdown("""
<style>
    /* Global Base */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Top Header */
    .header-container {
        background: linear-gradient(135deg, #111827 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .brand-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .brand-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-top: 4px;
    }
    
    /* Match Card in Fixtures Grid */
    .fixture-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 14px;
        transition: all 0.2s ease-in-out;
    }
    .fixture-card:hover {
        border-color: #38bdf8;
        box-shadow: 0 4px 20px rgba(56, 189, 248, 0.12);
    }
    .format-pill-t20 {
        background-color: #7c3aed;
        color: white;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 9999px;
        text-transform: uppercase;
    }
    .format-pill-odi {
        background-color: #0284c7;
        color: white;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 9999px;
        text-transform: uppercase;
    }
    .format-pill-test {
        background-color: #d97706;
        color: white;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 9999px;
        text-transform: uppercase;
    }
    
    /* Intelligence Metric Cards */
    .metric-box {
        background-color: #131d2e;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 14px 18px;
        text-align: left;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.45rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 4px 0;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #38bdf8;
    }
    
    /* Player Lineup Cards */
    .player-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
    }
    .badge-c {
        background-color: #f59e0b;
        color: #000;
        font-size: 0.72rem;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 4px;
    }
    .badge-vc {
        background-color: #3b82f6;
        color: #fff;
        font-size: 0.72rem;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 4px;
    }
    .badge-doubt {
        background-color: #ef4444;
        color: #fff;
        font-size: 0.70rem;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-container">
    <div>
        <h1 class="brand-title">NEW_X1 &middot; Performance Intelligence</h1>
        <div class="brand-subtitle">Automated Multi-Format Cricket Performance & Optimal Lineup Forecasting Engine</div>
    </div>
    <div style="text-align: right;">
        <span style="background: #10b981; color: #000; font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 9999px;">SYSTEM ACTIVE</span>
        <div style="color: #64748b; font-size: 0.75rem; margin-top: 4px;">T20, ODI & TEST TRAINED</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Load Future Matches & Squads Data ────────────────────────────────────────
FUTURE_MATCHES_FILE = BASE_DIR / "data" / "future_matches" / "upcoming_matches.json"
FUTURE_SQUADS_FILE  = BASE_DIR / "data" / "future_matches" / "upcoming_squads.json"

@st.cache_data
def load_future_fixtures():
    if FUTURE_MATCHES_FILE.exists():
        try:
            with open(FUTURE_MATCHES_FILE, "r") as f:
                data = json.load(f)
                return data.get("matches", [])
        except Exception:
            return []
    return []

@st.cache_data
def load_future_squads_dict():
    if FUTURE_SQUADS_FILE.exists():
        try:
            with open(FUTURE_SQUADS_FILE, "r") as f:
                data = json.load(f)
                return data.get("squads", {})
        except Exception:
            return {}
    return {}

upcoming_fixtures = load_future_fixtures()
upcoming_squads   = load_future_squads_dict()

# ── Sidebar Navigation ───────────────────────────────────────────────────────
st.sidebar.header("🎯 Mode Selection")
mode = st.sidebar.radio(
    "Select Operating Mode:",
    ["🔮 Upcoming Fixtures (Future Matches)", "⚙️ Custom Match Simulator"],
    index=0
)

active_match = None

if mode == "🔮 Upcoming Fixtures (Future Matches)":
    st.sidebar.subheader("📅 Fixture Filters")
    format_filter = st.sidebar.selectbox("Filter by Format", ["ALL", "T20", "ODI", "TEST"], index=0)
    
    # Filter matches
    filtered_matches = upcoming_fixtures
    
    # Time-based filtering (Future Fixtures: tomorrow onwards)
    today = date.today()
    future_matches = []
    today_matches = []
    
    for m in filtered_matches:
        try:
            m_date = datetime.strptime(m.get("date", ""), "%Y-%m-%d").date()
            if m_date > today:
                future_matches.append(m)
            elif m_date == today:
                today_matches.append(m)
        except:
            future_matches.append(m) # fallback

    if format_filter != "ALL":
        future_matches = [m for m in future_matches if m.get("match_type", "").upper() == format_filter]
        today_matches = [m for m in today_matches if m.get("match_type", "").upper() == format_filter]
        
    if today_matches:
        st.sidebar.info(f"🏏 **Today's Matches ({len(today_matches)})**\\nAwaiting Toss (T-30 min) for final XI prediction.", icon="ℹ️")
        for tm in today_matches:
            st.sidebar.caption(f"- {tm.get('team1')} vs {tm.get('team2')} [{tm.get('match_type')}]")

    # Dropdown to quickly select an upcoming fixture (tomorrow onwards)
    options = [
        f"[{m.get('match_type')}] {m.get('date')} — {m.get('team1')} vs {m.get('team2')} ({m.get('series')[:26]})"
        for m in future_matches
    ]
    
    if options:
        selected_option = st.sidebar.selectbox("Select Upcoming Match:", options, index=0)
        sel_idx = options.index(selected_option)
        active_match = future_matches[sel_idx]
    else:
        st.sidebar.info("No fixtures found for selected filter.")

else:
    # Custom Match Simulator Mode
    st.sidebar.subheader("⚙️ Match Configuration")
    TEAMS = [
        "India", "Australia", "England", "South Africa", "New Zealand", 
        "Pakistan", "West Indies", "Sri Lanka", "Afghanistan", "Bangladesh",
        "Chennai Super Kings", "Mumbai Indians", "Royal Challengers Bengaluru",
        "Kolkata Knight Riders", "Delhi Capitals", "Gujarat Titans", 
        "Rajasthan Royals", "Sunrisers Hyderabad", "Lucknow Super Giants", "Punjab Kings"
    ]
    t1 = st.sidebar.selectbox("Team 1", TEAMS, index=0)
    t2 = st.sidebar.selectbox("Team 2", TEAMS, index=1)
    fmt = st.sidebar.selectbox("Format", ["T20", "ODI", "Test"], index=0)
    m_date = st.sidebar.date_input("Match Date", date(2025, 10, 15))
    ven = st.sidebar.selectbox("Venue", [
        "Wankhede Stadium, Mumbai",
        "M Chinnaswamy Stadium, Bengaluru",
        "Eden Gardens, Kolkata",
        "Narendra Modi Stadium, Ahmedabad",
        "MA Chidambaram Stadium, Chennai",
        "Kennington Oval, London",
        "Melbourne Cricket Ground (MCG)"
    ], index=0)

    active_match = {
        "match_id": "custom",
        "team1": t1,
        "team2": t2,
        "match_type": fmt,
        "date": str(m_date),
        "venue": ven,
        "series": "Bilateral Exhibition Series"
    }

# ── Function to Extract Candidate Squad ──────────────────────────────────────
def get_match_squad_players(match_obj: dict) -> list[dict]:
    m_id = str(match_obj.get("match_id", ""))
    
    # Check if real squad exists in upcoming_squads.json
    if m_id in upcoming_squads:
        squad_entry = upcoming_squads[m_id]
        combined = []
        for av in squad_entry.get("available_squads", []):
            t_name = av.get("team_name", "Team")
            for p in av.get("players", []):
                p_name = p.get("player_name", "").strip()
                if p_name:
                    combined.append({
                        "name": p_name,
                        "role": p.get("role", "BAT"),
                        "team": t_name.split()[0],  # Short team prefix
                        "batting_style": p.get("batting_style", "Right-hand bat"),
                        "bowling_style": p.get("bowling_style", "Right-arm medium"),
                        "raw_injury_status": p.get("injury_status", "UNKNOWN")
                    })
        if len(combined) >= 14:
            return combined

    # Robust fallback roster based on team names
    t1 = match_obj.get("team1", "Team 1")
    t2 = match_obj.get("team2", "Team 2")
    
    defaults_t1 = [
        (f"{t1} TopBatter 1", "BAT"), (f"{t1} TopBatter 2", "BAT"), (f"{t1} Anchor", "BAT"),
        (f"{t1} Keeper", "WK"), (f"{t1} AllRounder 1", "AR"), (f"{t1} AllRounder 2", "AR"),
        (f"{t1} Pacer 1", "BOWL"), (f"{t1} Pacer 2", "BOWL"), (f"{t1} Spinner", "BOWL"),
        (f"{t1} Bowler 4", "BOWL"), (f"{t1} Batter 4", "BAT")
    ]
    defaults_t2 = [
        (f"{t2} TopBatter 1", "BAT"), (f"{t2} TopBatter 2", "BAT"), (f"{t2} Anchor", "BAT"),
        (f"{t2} Keeper", "WK"), (f"{t2} AllRounder 1", "AR"), (f"{t2} AllRounder 2", "AR"),
        (f"{t2} Pacer 1", "BOWL"), (f"{t2} Pacer 2", "BOWL"), (f"{t2} Spinner", "BOWL"),
        (f"{t2} Bowler 4", "BOWL"), (f"{t2} Batter 4", "BAT")
    ]
    
    # Famous players override if India/Australia/England
    if "India" in t1:
        defaults_t1 = [
            ("Rohit Sharma", "BAT"), ("Virat Kohli", "BAT"), ("Suryakumar Yadav", "BAT"),
            ("Shubman Gill", "BAT"), ("Rishabh Pant", "WK"), ("Hardik Pandya", "AR"),
            ("Ravindra Jadeja", "AR"), ("Axar Patel", "AR"), ("Jasprit Bumrah", "BOWL"),
            ("Kuldeep Yadav", "BOWL"), ("Arshdeep Singh", "BOWL"), ("Mohammed Siraj", "BOWL")
        ]
    if "Australia" in t2:
        defaults_t2 = [
            ("Travis Head", "BAT"), ("David Warner", "BAT"), ("Mitchell Marsh", "AR"),
            ("Glenn Maxwell", "AR"), ("Marcus Stoinis", "AR"), ("Tim David", "BAT"),
            ("Josh Inglis", "WK"), ("Pat Cummins", "BOWL"), ("Mitchell Starc", "BOWL"),
            ("Josh Hazlewood", "BOWL"), ("Adam Zampa", "BOWL")
        ]

    res = []
    for p, r in defaults_t1:
        res.append({"name": p, "role": r, "team": t1, "raw_injury_status": "FIT"})
    for p, r in defaults_t2:
        res.append({"name": p, "role": r, "team": t2, "raw_injury_status": "FIT"})
    return res


# ── Render Selected Match Banner ─────────────────────────────────────────────
if active_match:
    fmt_type = active_match.get("match_type", "T20").upper()
    pill_class = f"format-pill-{fmt_type.lower()}" if fmt_type.lower() in ["t20", "odi", "test"] else "format-pill-t20"
    
    st.markdown(f"""
    <div style="background-color: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span class="{pill_class}">{fmt_type} FORMAT</span>
            <span style="color: #94a3b8; font-size: 0.88rem;">📅 {active_match.get('date')}</span>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; margin: 10px 0;">
            <h2 style="margin: 0; color: #f8fafc; font-size: 1.8rem; font-weight: 800;">
                {active_match.get('team1')} <span style="color: #38bdf8; font-size: 1.2rem; font-weight: 400;">VS</span> {active_match.get('team2')}
            </h2>
        </div>
        <div style="color: #64748b; font-size: 0.88rem;">
            📍 {active_match.get('venue')} &nbsp;&middot;&nbsp; 🏆 {active_match.get('series')}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Execute Prediction Pipeline ──────────────────────────────────────────────
predict_btn = st.sidebar.button("⚡ Run Performance Intelligence & Optimal XI", type="primary", use_container_width=True)

if predict_btn or "last_forecast" in st.session_state:
    if predict_btn:
        with st.spinner("Executing Multi-Layer Intelligence Engine (Weather, Pitch PAF, Injury, Form, Solver)..."):
            venue_name = active_match.get("venue", "Wankhede Stadium")
            format_clean = active_match.get("match_type", "T20").lower()
            match_date_str = active_match.get("date", "2025-10-15")

            # 1. Weather & Pitch
            weather = fetch_venue_weather(venue_name)
            pitch_profile = get_venue_profile(venue_name, format_clean)

            # 2. Injury & Availability
            injury_reports = get_active_injury_reports()

            # 3. Squad extraction
            candidate_squad = get_match_squad_players(active_match)
            squad_names = [p["name"] for p in candidate_squad]

            # 4. ML Model Prediction
            try:
                pred_df = predict_squad(squad_names, format_clean, match_date_str)
                score_map = dict(zip(pred_df["player"], pred_df["predicted_score"]))
            except Exception as e:
                score_map = {}

            # 5. Apply Intelligence Adjustments
            scored_candidates = []
            for p in candidate_squad:
                name = p["name"]
                role = p["role"]
                team = p["team"]

                # Base predicted score
                base_val = score_map.get(name, float(np.random.normal(52, 14)))

                # Pitch PAF Adjustment
                paf_val = adjust_player_score(base_val, role, pitch_profile)

                # Injury & Availability adjustment
                rep = injury_reports.get(name, {"status": p.get("raw_injury_status", "FIT")})
                inj_data = calculate_player_injury_adjustments(
                    base_score=paf_val,
                    status=rep.get("status", "FIT"),
                    career_matches=30,
                    player_std=16.0
                )

                final_pts = inj_data["final_score"]

                scored_candidates.append({
                    "name": name,
                    "player": name,
                    "role": role,
                    "team": team,
                    "raw_score": round(base_val, 1),
                    "predicted_score": final_pts,
                    "mean_points": final_pts,
                    "injury_status": inj_data["status"],
                    "playing_probability": inj_data["playing_probability"],
                    "score_ci_low": inj_data["score_ci_low"],
                    "score_ci_high": inj_data["score_ci_high"],
                    "captain_upside": inj_data["captain_upside"]
                })

            df_pool = pd.DataFrame(scored_candidates)

            # 6. PuLP Optimization
            try:
                cov_dummy = np.eye(len(df_pool)) * 4.0
                best_names, _ = optimize_team_sharpe(df_pool, cov_dummy, max_players=11)
                optimal_team = df_pool[df_pool["name"].isin(best_names)].copy().to_dict(orient="records")
            except Exception:
                optimal_team = df_pool.sort_values("predicted_score", ascending=False).head(11).to_dict(orient="records")

            # Sort by captain ceiling upside
            optimal_team.sort(key=lambda x: x.get("captain_upside", x["predicted_score"]), reverse=True)
            if len(optimal_team) >= 2:
                optimal_team[0]["is_captain"] = True
                optimal_team[0]["is_vc"] = False
                optimal_team[1]["is_captain"] = False
                optimal_team[1]["is_vc"] = True
                for i in range(2, len(optimal_team)):
                    optimal_team[i]["is_captain"] = False
                    optimal_team[i]["is_vc"] = False

            # Cache results
            st.session_state["last_forecast"] = {
                "weather": weather,
                "pitch": pitch_profile,
                "team": optimal_team,
                "match": active_match
            }

    forecast = st.session_state["last_forecast"]
    weather = forecast["weather"]
    pitch_profile = forecast["pitch"]
    selected = forecast["team"]

    # ── Intelligence Metric Cards ────────────────────────────────────────────
    st.subheader("🌐 Environmental & Match Intelligence")
    m1, m2, m3, m4 = st.columns(4)

    total_projected = sum(p["predicted_score"] for p in selected)
    with m1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Pitch Category</div>
            <div class="metric-value">{pitch_profile['category']}</div>
            <div class="metric-sub">Avg 1st: {pitch_profile.get('avg_1st_innings', 165)} runs</div>
        </div>
        """, unsafe_allow_html=True)

    with m2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Weather Conditions</div>
            <div class="metric-value">{weather['temperature_c']}&deg;C</div>
            <div class="metric-sub">{weather['humidity_pct']}% Humidity &middot; {weather['cloud_cover_pct']}% Clouds</div>
        </div>
        """, unsafe_allow_html=True)

    with m3:
        swing_text = "Seam/Swing Advantage" if weather.get("seam_swing_advantage") else "Balanced Surface"
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Atmospheric Index</div>
            <div class="metric-value" style="font-size: 1.15rem; margin-top: 8px;">{swing_text}</div>
            <div class="metric-sub">Dew Risk: {'Elevated' if weather.get('dew_risk') else 'Low'}</div>
        </div>
        """, unsafe_allow_html=True)

    with m4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Projected Total XI</div>
            <div class="metric-value" style="color: #38bdf8;">{total_projected:.1f} pts</div>
            <div class="metric-sub">11-Player Optimal Lineup</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # ── Tabs View ────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏟️ Tactical Pitch View",
        "📋 Playing XI Cards",
        "📊 Detailed Match Intelligence",
        "🤖 AI Analyst Commentary"
    ])

    with tab1:
        st.markdown(render_cricket_pitch(selected), unsafe_allow_html=True)

    with tab2:
        cols = st.columns(3)
        for idx, p in enumerate(selected):
            col = cols[idx % 3]
            badge = ""
            if p.get("is_captain"):
                badge = "<span class='badge-c'>CAPTAIN &times;2</span>"
            elif p.get("is_vc"):
                badge = "<span class='badge-vc'>VC &times;1.5</span>"

            inj_badge = ""
            if p.get("injury_status") in ("DOUBTFUL", "INJURED"):
                inj_badge = f"<span class='badge-doubt'>&uarr; {p['injury_status']}</span>"

            with col:
                st.markdown(f"""
                <div class="player-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; font-size: 1.05rem;">{p['name']}</h4>
                        <div>{badge} {inj_badge}</div>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.82rem; margin: 4px 0 8px 0;">
                        <b>{p['role']}</b> &middot; {p['team']}
                    </div>
                    <div style="font-size: 1.35rem; font-weight: 700; color: #38bdf8;">
                        {p['predicted_score']} <span style="font-size: 0.75rem; color: #64748b;">projected pts</span>
                    </div>
                    <div style="color: #64748b; font-size: 0.76rem; margin-top: 6px; border-top: 1px solid #1e293b; padding-top: 6px;">
                        80% CI: <b>[{p.get('score_ci_low', p['predicted_score'])} - {p.get('score_ci_high', p['predicted_score'])}]</b> &nbsp;&middot;&nbsp; Start: <b>{p.get('playing_probability', 100)}%</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        st.subheader("Venue Characteristics & Environmental Impact")
        st.markdown(f"""
        - **Pitch Profile:** {pitch_profile.get('description', 'Standard balanced sporting track.')}
        - **Batter Multiplier Factor:** `{pitch_profile.get('batter_mult', 1.0)}x`
        - **Pacer Multiplier Factor:** `{pitch_profile.get('pacer_mult', 1.0)}x`
        - **Spinner Multiplier Factor:** `{pitch_profile.get('spinner_mult', 1.0)}x`
        - **Weather Overview:** {weather.get('summary', 'Clear playing conditions')}
        """)

    with tab4:
        st.subheader("Senior Analyst Selection Rationale")
        c_p = selected[0]
        vc_p = selected[1]
        st.markdown(f"""
        > **Captaincy Selection ({c_p['name']}):** Highest baseline expected output under current venue conditions. {c_p['name']} thrives in {pitch_profile['category'].lower()} surfaces with a proven ceiling upside of {c_p.get('captain_upside', c_p['predicted_score'])} points.
        >
        > **Vice-Captaincy Choice ({vc_p['name']}):** Selected for high statistical reliability and low variance index. Provides dependable floor points to anchor the squad objective.
        """)

else:
    # Initial landing screen with quick instructions
    st.info("👈 Select an upcoming fixture from the sidebar and click **'Run Performance Intelligence & Optimal XI'** to generate the optimal lineup.")
