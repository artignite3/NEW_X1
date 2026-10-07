"""Actual held-out evaluation only; never substitute simulated metrics."""
import sys
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from model.predict_model import evaluate_on_test, get_model

st.set_page_config(page_title="NEW_X1 Model Evaluation", layout="wide")
st.title("Model evaluation")
st.caption("Saved models train through 2025-06-30. Evaluation uses completed held-out matches only.")
fmt = st.sidebar.selectbox("Format", ["t20", "odi", "test"])
start = st.sidebar.date_input("Test start", date(2025, 7, 1), min_value=date(2025, 7, 1), max_value=date.today() - timedelta(days=1))
end = st.sidebar.date_input("Test end", date.today() - timedelta(days=1), min_value=date(2025, 7, 1), max_value=date.today() - timedelta(days=1))
if st.sidebar.button("Run evaluation", type="primary"):
    st.session_state.pop("evaluation", None)
    try:
        with st.spinner("Evaluating saved model on real match data..."):
            frame = evaluate_on_test(fmt, str(start), str(end))
        if frame.empty:
            st.warning("No completed matches in this window. Refresh the source data or choose another window.")
        else:
            st.session_state["evaluation"] = (fmt, start, end, frame)
    except Exception as error:
        st.error(f"Evaluation failed: {error}")

if "evaluation" in st.session_state:
    actual_fmt, actual_start, actual_end, frame = st.session_state["evaluation"]
    st.caption(f"Results: {actual_fmt.upper()}, {actual_start} to {actual_end}; latest observed match {frame.match_date.max()}")
    a, b, c = st.columns(3)
    a.metric("Matches", len(frame))
    b.metric("Mean selection regret (points)", f"{frame.selection_regret.mean():.2f}")
    c.metric("Mean player prediction MAE", f"{frame.player_mae.mean():.2f}")
    st.caption("Selection regret = actual best unconstrained XI score minus the actual score of the predicted top XI. It is distinct from player prediction MAE and does not benchmark the constrained product solver.")
    st.dataframe(frame, use_container_width=True)
    st.plotly_chart(px.histogram(frame, x="selection_regret", nbins=30), use_container_width=True)
    st.download_button("Download actual results", frame.to_csv(index=False).encode("utf-8"),
                       file_name=f"evaluation_{actual_fmt}_{actual_start}_to_{actual_end}.csv", mime="text/csv")
