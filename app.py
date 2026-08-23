import os, re
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title="LeadHunter AI v2.2", page_icon="🏠", layout="wide")

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

def get_key():
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return os.getenv("OPENAI_API_KEY")

def extract(text):
    x = text.lower()
    d = {}
    for p in ["1 bhk", "2 bhk", "3 bhk", "4 bhk", "plot", "commercial"]:
        if p in x:
            d["property_type"] = p.upper()
            break
    m = re.search(r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*(lakh|lac|crore|cr)", x)
    if m:
        d["budget"] = f"₹{m.group(1)} {m.group(2)}"
    for a in ["cidco", "vazirabad", "taroda", "shivaji nagar", "airport road",
              "miyapur", "hafeezpet"]:
        if a in x:
            d["area"] = a.title()
            break
    if "ready for move" in x or "ready to move" in x or "ready possession" in x:
        d["possession"] = "Ready to move"
    elif "under construction" in x:
        d["possession"] = "Under construction"
    if "within 1 month" in x or "this month" in x or "next month" in x or "urgent" in x:
        d["timeline"] = "Within 1 month"
    elif "1-3 month" in x or "1–3 month" in x or "2 month" in x or "3 month" in x:
        d["timeline"] = "1–3 months"
    elif "6 month" in x:
        d["timeline"] = "3–6 months"
    return d

def merge_fields(old, new):
    out = dict(old)
    for k, v in new.items():
        if v:
            out[k] = v
    return out

def score(d):
    s = 10
    s += 20 if d.get("budget") else 0
    s += 15 if d.get("area") else 0
    s += 15 if d.get("property_type") else 0
    s += 10 if d.get("possession") else 0
    s += 20 if d.get("timeline") == "Within 1 month" else 12 if d.get("timeline") == "1–3 months" else 6 if d.get("timeline") == "3–6 months" else 0
    return min(s, 100)

def temperature(s):
    return "🔥 HOT" if s >= 80 else "🟠 WARM" if s >= 55 else "⚪ COLD"

def fallback_reply(user_text, data):
    text = user_text.strip().lower()
    # Friendly opening: don't jump into qualification after a simple greeting.
    greetings = {"hi", "hello", "hey", "hii", "hiii", "good morning", "good afternoon", "good evening"}
    if text in greetings:
        return "Hi! 👋 Welcome. I can help you find a suitable property. What are you looking for?"
    if not data.get("property_type"):
        return "Sure 👍 Tell me what type of property you're looking for, and I'll help narrow it down."
    if not data.get("budget"):
        return "Got it 👍 What's your approximate budget?"
    if not data.get("area"):
        return "Great. Which area or locality would you prefer?"
    if not data.get("possession"):
        return "And do you prefer ready-to-move or under-construction?"
    if not data.get("timeline"):
        return "When are you planning to purchase?"
    return (
        f"Perfect 👍 I've captured your requirement: {data.get('property_type')} "
        f"in {data.get('area')} around {data.get('budget')}, "
        f"{data.get('possession').lower()}, purchase planned "
        f"{data.get('timeline').lower()}. I've recorded these details for the property consultant."
    )

def ai_reply(user_text, history, data):
    key = get_key()
    if not (key and OpenAI):
        return fallback_reply(user_text, data)

    client = OpenAI(api_key=key)
    system = f"""You are LeadHunter AI, a friendly real-estate enquiry assistant.

Current collected buyer information:
{data}

Conversation rules:
1. If the user's message is only a greeting such as Hi, Hello, Hey, Good morning, etc., DO NOT ask a detailed property question. Reply warmly and ask an open-ended question such as "What are you looking for?"
2. Never ask for information that is already present in Current collected buyer information.
3. Ask only ONE next question at a time.
4. Keep replies short, natural and WhatsApp-friendly.
5. If the buyer gives several details in one message, acknowledge them and ask only for the next missing detail.
6. When all key details are present, summarize them and say they have been captured for the property consultant.
7. Never invent property availability, prices, discounts, or promises.
Return only the customer-facing reply."""
    r = client.responses.create(
        model="gpt-5.6-luna",
        instructions=system,
        input=history + [{"role": "user", "content": user_text}]
    )
    return r.output_text

if "leads" not in st.session_state:
    st.session_state.leads = []
if "chat" not in st.session_state:
    st.session_state.chat = []
if "lead_data" not in st.session_state:
    st.session_state.lead_data = {}

st.title("🏠 LeadHunter AI v2.2")
st.caption("Conversational real-estate lead qualification — natural conversation")

t1, t2, t3 = st.tabs(["💬 Buyer Chat", "📊 Broker Dashboard", "⚙️ Setup"])

with t1:
    st.subheader("Natural conversation — friendly first, questions one at a time")

    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if st.session_state.lead_data:
        st.caption(
            "Captured: " +
            " • ".join(f"{k.replace('_',' ').title()}: {v}"
                       for k, v in st.session_state.lead_data.items())
        )

    prompt = st.chat_input("Example: I need a 2 BHK in CIDCO around ₹45 lakh")
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        new_data = extract(prompt)
        st.session_state.lead_data = merge_fields(st.session_state.lead_data, new_data)
        reply = ai_reply(prompt, st.session_state.chat[:-1], st.session_state.lead_data)
        st.session_state.chat.append({"role": "assistant", "content": reply})
        st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Save conversation as lead", use_container_width=True):
            d = st.session_state.lead_data
            s = score(d)
            transcript = " ".join(m["content"] for m in st.session_state.chat if m["role"] == "user")
            st.session_state.leads.append({
                "Time": datetime.now().strftime("%d-%m-%Y %H:%M"),
                "Requirement": d.get("property_type", ""),
                "Budget": d.get("budget", ""),
                "Area": d.get("area", ""),
                "Possession": d.get("possession", ""),
                "Timeline": d.get("timeline", ""),
                "Score": s,
                "Status": temperature(s),
                "Conversation": transcript
            })
            st.success(f"Saved — {temperature(s)} ({s}/100)")
            if s >= 80:
                st.error("🔥 BROKER ALERT: High-priority lead. Call quickly.")

    with c2:
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.chat = []
            st.session_state.lead_data = {}
            st.rerun()

with t2:
    st.subheader("Broker Dashboard")
    if st.session_state.leads:
        df = pd.DataFrame(st.session_state.leads).sort_values("Score", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "leadhunter_leads.csv", "text/csv")
    else:
        st.info("No saved leads yet.")

with t3:
    if get_key():
        st.success("OpenAI API key detected — AI mode enabled.")
    else:
        st.warning("No API key — demo memory mode is active.")
    st.write("Demo mode remembers collected details and handles greetings naturally.")
    st.write("For real AI mode, add OPENAI_API_KEY under Streamlit Secrets. Never put an API key in app.py or GitHub.")

st.divider()
st.caption("Prototype only. Verify property availability and prices before communicating them.")
