import os, re
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title="LeadHunter AI v2.1", page_icon="🏠", layout="wide")

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
    if "ready for move" in x or "ready to move" in x or "ready possession" in x or "ready for possession" in x:
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

def missing_question(d):
    if not d.get("property_type"):
        return "What property type are you looking for — for example, 2 BHK or 3 BHK?"
    if not d.get("budget"):
        return "What's your approximate budget?"
    if not d.get("area"):
        return "Which area would you prefer?"
    if not d.get("possession"):
        return "Do you want ready-to-move or under-construction?"
    if not d.get("timeline"):
        return "When are you planning to purchase?"
    return None

def fallback_reply(accumulated):
    q = missing_question(accumulated)
    if q:
        return q
    return (
        f"Perfect 👍 I have your requirement: {accumulated.get('property_type')} "
        f"in {accumulated.get('area')} around {accumulated.get('budget')}, "
        f"{accumulated.get('possession').lower()}, purchase planned "
        f"{accumulated.get('timeline').lower()}. "
        "I've captured these details for the property consultant."
    )

def ai_reply(user_text, history, accumulated):
    key = get_key()
    if not (key and OpenAI):
        return fallback_reply(accumulated)

    client = OpenAI(api_key=key)
    system = f"""You are LeadHunter AI, a concise real-estate lead qualification assistant.
The conversation has already collected these fields:
{accumulated}

IMPORTANT:
- Treat the collected fields as authoritative unless the buyer corrects them.
- NEVER ask again for a field that is already present.
- Ask ONLY for the first missing field.
- If all fields are present, summarize them and say they have been captured for the property consultant.
- Never invent property availability, prices or promises.
- Return only the customer-facing reply."""

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

st.title("🏠 LeadHunter AI v2.1")
st.caption("Conversational real-estate lead qualification — smarter memory")

t1, t2, t3 = st.tabs(["💬 Buyer Chat", "📊 Broker Dashboard", "⚙️ Setup"])

with t1:
    st.subheader("Talk naturally — no repeated questions")

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
            transcript = " ".join(
                m["content"] for m in st.session_state.chat if m["role"] == "user"
            )
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
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            "leadhunter_leads.csv",
            "text/csv"
        )
    else:
        st.info("No saved leads yet.")

with t3:
    if get_key():
        st.success("OpenAI API key detected — AI mode enabled.")
    else:
        st.warning("No API key — demo memory mode is active.")
    st.write("This version remembers details already provided and will not repeatedly ask for them.")
    st.write("For real AI mode, add OPENAI_API_KEY under Streamlit Secrets. Never put the key in app.py or GitHub.")

st.divider()
st.caption("Prototype only. Verify property availability and prices before communicating them.")
