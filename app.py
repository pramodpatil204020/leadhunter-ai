import os
from datetime import datetime
import pandas as pd
import streamlit as st

from lead_engine import extract, merge, next_missing, score, status, local_reply, FIELD_LABELS

st.set_page_config(page_title="LeadHunter AI", page_icon="🏠", layout="wide")

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def api_key():
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return os.getenv("OPENAI_API_KEY")


def ai_reply(user_text, history, memory):
    key = api_key()
    if not (key and OpenAI):
        return local_reply(user_text, memory)

    client = OpenAI(api_key=key)
    system = f"""
You are LeadHunter AI, a friendly human-like real-estate sales assistant.

BUYER MEMORY (authoritative):
{memory}

Rules:
- Behave like a helpful salesperson, not a form.
- A simple Hi/Hello/Hey gets a warm greeting and an open-ended question. Do not jump into a detailed questionnaire.
- Understand typos, short replies, natural language, and several facts in one message.
- Never ask for anything already present in BUYER MEMORY.
- "budget no issue", "any budget", "money no issue" means the budget is flexible and is a COMPLETE answer. Never ask the budget again.
- "any area" or "location flexible" means the area is flexible and is a COMPLETE answer.
- "2 or 3 BHK" is valid; do not force the buyer to choose one.
- "empty plot" or "open plot" means property type = Plot.
- For a Plot, NEVER ask ready-to-move/under-construction. Ask plot size instead.
- For flats/houses/commercial property, possession preference is relevant.
- Ask only ONE useful missing question at a time.
- If the user gives multiple facts, remember all of them and move to the next missing fact.
- If the buyer says "I already told you", use the memory and never repeat that question.
- Name and phone are optional and should not block qualification.
- Once the core requirement is complete, STOP asking qualification questions and offer the next action.
- Never invent property availability, prices, discounts, or promises.
- Keep replies concise and WhatsApp-friendly.
Return only the customer-facing reply.
"""
    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=system,
        input=history + [{"role": "user", "content": user_text}],
    )
    return response.output_text


if "chat" not in st.session_state:
    st.session_state.chat = []
if "lead_data" not in st.session_state:
    st.session_state.lead_data = {}
if "leads" not in st.session_state:
    st.session_state.leads = []

st.title("🏠 LeadHunter AI")
st.caption("Human-like real-estate lead qualification")

tab_chat, tab_dashboard, tab_setup = st.tabs(["💬 Buyer Chat", "📊 Broker Dashboard", "⚙️ Setup"])

with tab_chat:
    st.subheader("Talk naturally")

    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if st.session_state.lead_data:
        st.caption(
            "🧠 Remembered: " + " • ".join(
                f"{FIELD_LABELS.get(k, k)} = {v}"
                for k, v in st.session_state.lead_data.items() if v
            )
        )

    prompt = st.chat_input("Type naturally, e.g. Hi, I need a 2 BHK...")
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        st.session_state.lead_data = merge(st.session_state.lead_data, extract(prompt))
        reply = ai_reply(prompt, st.session_state.chat[:-1], st.session_state.lead_data)
        st.session_state.chat.append({"role": "assistant", "content": reply})
        st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Save lead", use_container_width=True):
            d = st.session_state.lead_data
            if not d:
                st.warning("Start a conversation first.")
            else:
                s = score(d)
                transcript = " ".join(m["content"] for m in st.session_state.chat if m["role"] == "user")
                st.session_state.leads.append({
                    "Time": datetime.now().strftime("%d-%m-%Y %H:%M"),
                    "Name": d.get("name", ""),
                    "Phone": d.get("phone", ""),
                    "Requirement": d.get("property_type", ""),
                    "Area": d.get("area", ""),
                    "Budget": d.get("budget", ""),
                    "Possession": d.get("possession", ""),
                    "Plot Size": d.get("plot_size", ""),
                    "Timeline": d.get("timeline", ""),
                    "Purpose": d.get("purpose", ""),
                    "Score": s,
                    "Status": status(s),
                    "Conversation": transcript,
                })
                st.success(f"Saved — {status(s)} ({s}/100)")
    with c2:
        if st.button("🗑️ New conversation", use_container_width=True):
            st.session_state.chat = []
            st.session_state.lead_data = {}
            st.rerun()

with tab_dashboard:
    st.subheader("📊 Broker Dashboard")
    if st.session_state.leads:
        df = pd.DataFrame(st.session_state.leads).sort_values("Score", ascending=False)
        a, b, c, d = st.columns(4)
        a.metric("Total", len(df))
        b.metric("🔥 Hot", int((df["Score"] >= 80).sum()))
        c.metric("🟠 Warm", int(((df["Score"] >= 55) & (df["Score"] < 80)).sum()))
        d.metric("⚪ Cold", int((df["Score"] < 55).sum()))
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download leads CSV", df.to_csv(index=False).encode("utf-8"), "leadhunter_leads.csv", "text/csv")
    else:
        st.info("No saved leads yet.")

with tab_setup:
    st.subheader("⚙️ Setup")
    if api_key():
        st.success("OpenAI AI mode is enabled.")
    else:
        st.info("Demo mode is active. The conversation engine works without an API key.")
    st.write("The production AI uses the OpenAI Responses API with GPT-5.6 Luna when OPENAI_API_KEY is configured.")
    st.write("Never put an API key inside app.py or GitHub.")

st.divider()
st.caption("Prototype. Verify property availability and prices before making commitments.")
