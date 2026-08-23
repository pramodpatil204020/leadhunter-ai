
import os
import re
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title="LeadHunter AI", page_icon="🏠", layout="wide")

# Optional OpenAI connection. The app remains usable without an API key.
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ---------- Conversation memory ----------
FIELDS = [
    "property_type", "budget", "area", "possession",
    "timeline", "purpose", "name", "phone"
]

FIELD_LABELS = {
    "property_type": "property type",
    "budget": "budget",
    "area": "preferred area",
    "possession": "possession preference",
    "timeline": "purchase timeline",
    "purpose": "purchase purpose",
    "name": "name",
    "phone": "phone number",
}


def get_api_key():
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return os.getenv("OPENAI_API_KEY")


def normalize(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def is_greeting(text):
    t = normalize(text)
    greetings = {
        "hi", "hello", "hey", "hii", "hiii", "helo",
        "good morning", "good afternoon", "good evening",
        "namaste", "hi there", "hello there"
    }
    return t in greetings or (
        len(t) <= 18 and any(t.startswith(g) for g in greetings)
    )


def is_no_preference(text, field):
    t = normalize(text)

    if field == "budget":
        phrases = [
            "budget no issue", "no budget", "budget is no issue",
            "any budget", "budget doesn't matter", "budget doesnt matter",
            "money no issue", "price no issue", "no problem with budget",
            "flexible budget", "budget flexible", "budget is flexible",
            "not a problem", "whatever budget", "any price"
        ]
        return any(p in t for p in phrases)

    if field == "area":
        phrases = [
            "any area", "anywhere", "no area preference",
            "area no issue", "location no issue", "any location",
            "location flexible", "area flexible", "any locality"
        ]
        return any(p in t for p in phrases)

    if field == "possession":
        return any(p in t for p in [
            "either", "anything is fine", "no preference",
            "doesn't matter", "doesnt matter", "any is fine"
        ])

    if field == "timeline":
        return any(p in t for p in [
            "no hurry", "not decided", "flexible", "anytime",
            "no fixed timeline", "no timeline"
        ])

    return False


def extract(text):
    """Extract multiple facts from one natural-language message."""
    x = normalize(text)
    d = {}

    # Property type: handle 2 or 3 BHK, 2/3 BHK, etc.
    if re.search(r"\b2\s*(?:or|/|and)\s*3\s*bhk\b", x):
        d["property_type"] = "2 or 3 BHK"
    else:
        m = re.search(r"\b([1-5])\s*bhk\b", x)
        if m:
            d["property_type"] = f"{m.group(1)} BHK"
        elif re.search(r"\bplot\b", x):
            d["property_type"] = "Plot"
        elif re.search(r"\bcommercial\b", x):
            d["property_type"] = "Commercial"

    # Budget
    if is_no_preference(x, "budget"):
        d["budget"] = "Flexible / no budget limit"
    else:
        m = re.search(
            r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*"
            r"(lakh|lac|lakhs|crore|cr)\b", x
        )
        if m:
            d["budget"] = f"₹{m.group(1)} {m.group(2)}"

    # Area / city
    areas = [
        "cidco", "vazirabad", "taroda", "shivaji nagar",
        "airport road", "miyapur", "hafeezpet", "kukatpally",
        "nanded", "hyderabad"
    ]
    found = [a for a in areas if a in x]
    if found:
        # Prefer the most specific locality, but retain city when relevant.
        d["area"] = ", ".join(dict.fromkeys(a.title() for a in found))

    # Possession
    if any(p in x for p in [
        "ready for move", "ready to move", "ready possession",
        "ready for possession", "immediate possession"
    ]):
        d["possession"] = "Ready to move"
    elif "under construction" in x:
        d["possession"] = "Under construction"
    elif is_no_preference(x, "possession"):
        d["possession"] = "No preference"

    # Timeline
    if any(p in x for p in [
        "within 1 month", "this month", "next month", "urgent",
        "immediately", "immediate"
    ]):
        d["timeline"] = "Within 1 month"
    elif re.search(r"\b[12]\s*(?:-|–|to)\s*3\s*months?\b", x):
        d["timeline"] = "1–3 months"
    elif "3 to 6 months" in x or "3-6 months" in x or "within 6 months" in x:
        d["timeline"] = "3–6 months"
    elif is_no_preference(x, "timeline"):
        d["timeline"] = "Flexible"

    # Purpose
    if any(p in x for p in ["for investment", "investment purpose", "investing"]):
        d["purpose"] = "Investment"
    elif any(p in x for p in ["for living", "to live", "self use", "self-use", "own use"]):
        d["purpose"] = "Self-use"

    # Name: simple "I'm Rohit", "my name is Rohit", "I am Rohit"
    m = re.search(r"\b(?:my name is|i am|i'm|im)\s+([a-zA-Z][a-zA-Z ]{1,30})\b", text, re.I)
    if m:
        candidate = m.group(1).strip()
        if candidate.lower() not in {"looking", "interested", "planning"}:
            d["name"] = candidate.title()

    # Phone
    m = re.search(r"\b(?:\+91[\s-]?)?([6-9]\d{9})\b", x)
    if m:
        d["phone"] = m.group(1)

    return d


def merge_memory(memory, new):
    result = dict(memory)
    for key, value in new.items():
        if value:
            result[key] = value
    return result


def has_value(memory, field):
    return bool(memory.get(field))


def next_missing(memory):
    # Name and phone are optional; don't interrogate a buyer for them.
    for field in ["property_type", "budget", "area", "possession", "timeline"]:
        if not has_value(memory, field):
            return field
    return None


def score_lead(memory):
    # "Flexible / no budget limit" counts as a supplied budget preference.
    score = 10
    score += 20 if memory.get("budget") else 0
    score += 15 if memory.get("area") else 0
    score += 15 if memory.get("property_type") else 0
    score += 10 if memory.get("possession") else 0
    score += 20 if memory.get("timeline") == "Within 1 month" else (
        12 if memory.get("timeline") == "1–3 months" else
        6 if memory.get("timeline") == "3–6 months" else 0
    )
    score += 5 if memory.get("phone") else 0
    return min(score, 100)


def temperature(score):
    return "🔥 HOT" if score >= 80 else ("🟠 WARM" if score >= 55 else "⚪ COLD")


def fallback_reply(user_text, memory, just_greeted=False):
    """Natural deterministic conversation when no API is configured."""
    t = normalize(user_text)

    if is_greeting(t):
        return "Hi! 👋 Welcome. I can help you find a suitable property. What are you looking for?"

    # If the user explicitly says they don't care about a field,
    # acknowledge it instead of asking for it again.
    missing = next_missing(memory)

    if missing == "property_type":
        return "Sure 👍 What type of property are you looking for — 2 BHK, 3 BHK, plot, or something else?"

    if missing == "budget":
        return "Got it 👍 What's your approximate budget? If you don't have a fixed budget, that's completely fine."

    if missing == "area":
        return "Great 👍 Which area or locality would you prefer? You can also say 'any area'."

    if missing == "possession":
        return "And do you prefer ready-to-move or under-construction? Either is fine if you have no preference."

    if missing == "timeline":
        return "When are you planning to purchase — soon, within a few months, or are you flexible?"

    # All core information is known.
    parts = [
        memory.get("property_type"),
        memory.get("area"),
        memory.get("budget"),
        memory.get("possession"),
        memory.get("timeline")
    ]
    return (
        "Perfect 👍 I have everything I need. "
        f"You're looking for {parts[0]} in {parts[1]}, "
        f"budget {parts[2]}, {str(parts[3]).lower()}, "
        f"with a {str(parts[4]).lower()} purchase timeline. "
        "I've captured the requirement for the property consultant. "
        "Would you like help arranging a call or viewing?"
    )


def ai_reply(user_text, history, memory):
    """Use OpenAI when configured; otherwise use the robust local conversation engine."""
    key = get_api_key()
    if not (key and OpenAI):
        return fallback_reply(user_text, memory)

    client = OpenAI(api_key=key)
    system = f"""
You are LeadHunter AI, a friendly, intelligent real-estate enquiry assistant.

CURRENT BUYER PROFILE (this is your memory):
{memory}

Rules:
- Behave like a good human salesperson, not a form.
- If the user only says Hi/Hello/Hey, greet them warmly and ask an open-ended question such as "What are you looking for?"
- Understand natural language, typos, short replies and implied answers.
- Treat "budget no issue", "any budget", "money no issue" etc. as a valid answer meaning the budget is flexible. NEVER ask for the budget again after that.
- Treat "any area", "location flexible", etc. as a valid answer meaning area is flexible. NEVER ask for it again.
- Remember every fact in the CURRENT BUYER PROFILE.
- Never ask again for a field that is already in the profile.
- If the user provides several facts in one message, capture all of them and ask only for the single most useful missing fact.
- Ask only ONE question at a time.
- If the user is unsure (e.g. "2 or 3 BHK"), accept it as a valid requirement instead of forcing a choice.
- Do not ask for name or phone unless naturally useful; those are optional.
- When all core property fields are known, stop qualifying. Summarize the requirement and offer the next action.
- Never invent properties, availability, prices, discounts, locations, or promises.
- Keep replies short, natural and WhatsApp-friendly.
Return ONLY the customer-facing reply.
"""
    r = client.responses.create(
        model="gpt-5.6-luna",
        instructions=system,
        input=history + [{"role": "user", "content": user_text}]
    )
    return r.output_text


# ---------- App state ----------
if "leads" not in st.session_state:
    st.session_state.leads = []
if "chat" not in st.session_state:
    st.session_state.chat = []
if "lead_data" not in st.session_state:
    st.session_state.lead_data = {}


# ---------- UI ----------
st.title("🏠 LeadHunter AI")
st.caption("Human-like real-estate lead qualification")

tab1, tab2, tab3 = st.tabs(["💬 Buyer Chat", "📊 Broker Dashboard", "⚙️ Setup"])

with tab1:
    st.subheader("Talk naturally")

    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if st.session_state.lead_data:
        st.caption(
            "🧠 Remembered: " +
            " • ".join(
                f"{FIELD_LABELS.get(k, k)} = {v}"
                for k, v in st.session_state.lead_data.items()
                if v
            )
        )

    prompt = st.chat_input("Type naturally, e.g. Hi, I need a 2 BHK...")
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})

        # Extract facts BEFORE generating the reply, so the assistant sees
        # the new answer immediately.
        new_facts = extract(prompt)
        st.session_state.lead_data = merge_memory(
            st.session_state.lead_data, new_facts
        )

        reply = ai_reply(
            prompt,
            st.session_state.chat[:-1],
            st.session_state.lead_data
        )
        st.session_state.chat.append({"role": "assistant", "content": reply})
        st.rerun()

    c1, c2 = st.columns(2)

    with c1:
        if st.button("💾 Save lead", use_container_width=True):
            d = st.session_state.lead_data
            if not d:
                st.warning("Have a conversation first.")
            else:
                s = score_lead(d)
                transcript = " ".join(
                    m["content"] for m in st.session_state.chat
                    if m["role"] == "user"
                )
                st.session_state.leads.append({
                    "Time": datetime.now().strftime("%d-%m-%Y %H:%M"),
                    "Name": d.get("name", ""),
                    "Phone": d.get("phone", ""),
                    "Requirement": d.get("property_type", ""),
                    "Budget": d.get("budget", ""),
                    "Area": d.get("area", ""),
                    "Possession": d.get("possession", ""),
                    "Timeline": d.get("timeline", ""),
                    "Purpose": d.get("purpose", ""),
                    "Score": s,
                    "Status": temperature(s),
                    "Conversation": transcript,
                })
                st.success(f"Saved — {temperature(s)} ({s}/100)")
                if s >= 80:
                    st.error("🔥 BROKER ALERT: High-priority lead. Call quickly.")

    with c2:
        if st.button("🗑️ New conversation", use_container_width=True):
            st.session_state.chat = []
            st.session_state.lead_data = {}
            st.rerun()


with tab2:
    st.subheader("📊 Broker Dashboard")

    if st.session_state.leads:
        df = pd.DataFrame(st.session_state.leads).sort_values(
            "Score", ascending=False
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(df))
        c2.metric("🔥 Hot", int((df["Score"] >= 80).sum()))
        c3.metric("🟠 Warm", int(((df["Score"] >= 55) & (df["Score"] < 80)).sum()))
        c4.metric("⚪ Cold", int((df["Score"] < 55).sum()))

        st.dataframe(df, use_container_width=True, hide_index=True)

        st.download_button(
            "Download leads CSV",
            df.to_csv(index=False).encode("utf-8"),
            "leadhunter_leads.csv",
            "text/csv",
        )
    else:
        st.info("No leads saved yet.")


with tab3:
    st.subheader("⚙️ AI Setup")

    if get_api_key():
        st.success("OpenAI API key detected — AI conversation mode is enabled.")
    else:
        st.info(
            "Demo mode is active. It already understands greetings, short replies, "
            "flexible budgets, flexible areas, multiple details and conversation memory."
        )
        st.write(
            "For production AI, add OPENAI_API_KEY in Streamlit Secrets. "
            "Never put an API key in app.py or GitHub."
        )

    st.markdown("### Conversation behaviour")
    st.write("• Hi → friendly greeting, not an interrogation")
    st.write("• '2 or 3 BHK' → accepted as a valid requirement")
    st.write("• 'Budget no issue' → remembered as flexible budget")
    st.write("• 'Any area' → remembered as flexible location")
    st.write("• Details already given → never asked again")
    st.write("• Only one useful question at a time")
    st.write("• Once qualified → stop questioning and offer the next action")

st.divider()
st.caption("Prototype. Verify property availability and prices before making commitments.")
