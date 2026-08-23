import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="LeadHunter AI", page_icon="🏠", layout="wide")

if "leads" not in st.session_state:
    st.session_state.leads = []

def score_lead(budget, area, property_type, timeline, possession, phone):
    score = 10
    if budget: score += 20
    if area: score += 15
    if property_type: score += 15
    if possession: score += 10
    if phone: score += 10
    if timeline == "Within 1 month": score += 20
    elif timeline == "1–3 months": score += 12
    elif timeline == "3–6 months": score += 6
    return min(score, 100)

def temperature(score):
    if score >= 80: return "🔥 HOT"
    if score >= 55: return "🟠 WARM"
    return "⚪ COLD"

st.title("🏠 LeadHunter AI")
st.caption("Real-estate lead qualification demo — prototype only")

tab1, tab2, tab3 = st.tabs(["Buyer Demo", "Broker Dashboard", "How it works"])

with tab1:
    st.subheader("Qualify a new property enquiry")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Buyer name", placeholder="Rahul")
        phone = st.text_input("Phone / WhatsApp", placeholder="98XXXXXXXX")
        property_type = st.selectbox("Requirement", ["", "1 BHK", "2 BHK", "3 BHK", "Plot", "Commercial"])
        budget = st.text_input("Budget", placeholder="₹45 lakh")
    with c2:
        area = st.text_input("Preferred area", placeholder="Vazirabad / CIDCO")
        possession = st.selectbox("Possession", ["", "Ready to move", "Under construction", "Either"])
        timeline = st.selectbox("Purchase timeline", ["Just exploring", "3–6 months", "1–3 months", "Within 1 month"])
        source = st.selectbox("Lead source", ["WhatsApp", "Website", "Phone", "Property portal", "Walk-in"])

    score = score_lead(budget, area, property_type, timeline, possession, phone)
    st.metric("Live lead score", f"{score}/100", temperature(score))

    if st.button("Qualify & save lead", type="primary", use_container_width=True):
        lead = {
            "Time": datetime.now().strftime("%d-%m-%Y %H:%M"),
            "Name": name or "Unknown",
            "Phone": phone,
            "Requirement": property_type,
            "Budget": budget,
            "Area": area,
            "Possession": possession,
            "Timeline": timeline,
            "Source": source,
            "Score": score,
            "Status": temperature(score),
        }
        st.session_state.leads.append(lead)
        st.success(f"Lead saved: {temperature(score)} — {score}/100")
        if score >= 80:
            st.error(f"🔥 BROKER ALERT: Call {lead['Name']} quickly. {property_type}, {budget}, {area}, {timeline}.")
        elif score >= 55:
            st.warning("🟠 Follow up soon and clarify remaining buying criteria.")
        else:
            st.info("⚪ Keep in nurture list; avoid spending too much broker time yet.")

with tab2:
    st.subheader("Broker Dashboard")
    if st.session_state.leads:
        df = pd.DataFrame(st.session_state.leads).sort_values("Score", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        hot = (df["Score"] >= 80).sum()
        warm = ((df["Score"] >= 55) & (df["Score"] < 80)).sum()
        cold = (df["Score"] < 55).sum()
        a,b,c,d = st.columns(4)
        a.metric("Total", len(df))
        b.metric("Hot", int(hot))
        c.metric("Warm", int(warm))
        d.metric("Cold", int(cold))
        st.download_button("Download leads CSV", df.to_csv(index=False).encode("utf-8"), "leads.csv", "text/csv")
    else:
        st.info("No leads yet. Add one in Buyer Demo.")

with tab3:
    st.subheader("Prototype workflow")
    st.code("""Buyer enquiry
      ↓
Collect requirement, budget, area & timeline
      ↓
Score 0–100
      ↓
HOT / WARM / COLD
      ↓
Save to broker dashboard
      ↓
Alert broker for HOT leads
      ↓
Future version: AI chat + WhatsApp + automated follow-ups""")
    st.write("This version deliberately uses deterministic scoring, so we can test the business idea before paying for APIs.")
