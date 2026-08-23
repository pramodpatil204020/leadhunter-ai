import os,re
from datetime import datetime
import pandas as pd
import streamlit as st
st.set_page_config(page_title="LeadHunter AI v2",page_icon="🏠",layout="wide")
try:
    from openai import OpenAI
except Exception:
    OpenAI=None
def key():
    try:return st.secrets["OPENAI_API_KEY"]
    except Exception:return os.getenv("OPENAI_API_KEY")
def extract(t):
    x=t.lower(); d={"property_type":"","budget":"","area":"","possession":"","timeline":"Just exploring"}
    for p in ["1 bhk","2 bhk","3 bhk","4 bhk","plot","commercial"]:
        if p in x:d["property_type"]=p.upper();break
    m=re.search(r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*(lakh|lac|crore|cr)",x)
    if m:d["budget"]=f"₹{m.group(1)} {m.group(2)}"
    for a in ["cidco","vazirabad","taroda","shivaji nagar","airport road","miyapur","hafeezpet"]:
        if a in x:d["area"]=a.title();break
    if "ready" in x:d["possession"]="Ready to move"
    elif "under construction" in x:d["possession"]="Under construction"
    if "within 1 month" in x or "this month" in x or "urgent" in x:d["timeline"]="Within 1 month"
    elif "1-3 month" in x or "2 month" in x or "3 month" in x:d["timeline"]="1–3 months"
    elif "6 month" in x:d["timeline"]="3–6 months"
    return d
def score(d):
    s=10+20*bool(d["budget"])+15*bool(d["area"])+15*bool(d["property_type"])+10*bool(d["possession"])
    s+=20 if d["timeline"]=="Within 1 month" else 12 if d["timeline"]=="1–3 months" else 6 if d["timeline"]=="3–6 months" else 0
    return min(s,100)
def temp(s):return "🔥 HOT" if s>=80 else "🟠 WARM" if s>=55 else "⚪ COLD"
def reply(msg,hist):
    if key() and OpenAI:
        c=OpenAI(api_key=key())
        r=c.responses.create(model="gpt-5.6-luna",instructions="""You are LeadHunter AI, a concise real-estate lead qualifier. Collect property type, budget, area, possession preference and purchase timeline. Ask at most 2 short questions. Never invent property availability, prices or promises. Return only the customer-facing reply.""",input=hist+[{"role":"user","content":msg}])
        return r.output_text
    d=extract(msg); missing=[]
    if not d["property_type"]:missing.append("property type")
    if not d["budget"]:missing.append("budget")
    if not d["area"]:missing.append("preferred area")
    if not d["possession"]:missing.append("ready-to-move or under-construction")
    if missing:return "Thanks! 👍 Could you tell me your "+ " and ".join(missing[:2])+"?"
    return f"Great — {d['property_type']} around {d['budget']} in {d['area']}. Are you looking to purchase {d['timeline'].lower()}?"
if "leads" not in st.session_state:st.session_state.leads=[]
if "chat" not in st.session_state:st.session_state.chat=[]
st.title("🏠 LeadHunter AI v2");st.caption("Conversational real-estate lead qualification — prototype")
t1,t2,t3=st.tabs(["💬 Buyer Chat","📊 Broker Dashboard","⚙️ Setup"])
with t1:
    st.subheader("Talk naturally — no form required")
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):st.write(m["content"])
    p=st.chat_input("Example: I need a 2 BHK in CIDCO around ₹45 lakh")
    if p:
        st.session_state.chat += [{"role":"user","content":p},{"role":"assistant","content":reply(p,st.session_state.chat)}]
        st.rerun()
    c1,c2=st.columns(2)
    with c1:
        if st.button("Save conversation as lead",use_container_width=True):
            text=" ".join(m["content"] for m in st.session_state.chat if m["role"]=="user");d=extract(text);s=score(d)
            st.session_state.leads.append({"Time":datetime.now().strftime("%d-%m-%Y %H:%M"),**d,"Score":s,"Status":temp(s),"Conversation":text})
            st.success(f"Saved — {temp(s)} ({s}/100)")
            if s>=80:st.error("🔥 BROKER ALERT: High-priority lead. Call quickly.")
    with c2:
        if st.button("Clear chat",use_container_width=True):st.session_state.chat=[];st.rerun()
with t2:
    st.subheader("Broker Dashboard")
    if st.session_state.leads:
        df=pd.DataFrame(st.session_state.leads).sort_values("Score",ascending=False);st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("Download CSV",df.to_csv(index=False).encode(),"leadhunter_leads.csv","text/csv")
    else:st.info("No saved leads yet.")
with t3:
    if key():st.success("OpenAI API key detected — AI mode enabled.")
    else:st.warning("No API key — demo fallback mode is active.")
    st.write("For real AI, add OPENAI_API_KEY under Streamlit Secrets. Never put an API key in app.py or GitHub.")
    st.write("OpenAI API usage is billed separately from a ChatGPT subscription.")
st.divider();st.caption("Prototype only. Verify property availability and prices before communicating them.")
