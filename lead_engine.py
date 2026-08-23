import re

FIELD_LABELS = {
    "property_type": "property type",
    "area": "preferred area",
    "budget": "budget",
    "possession": "possession preference",
    "plot_size": "plot size",
    "timeline": "purchase timeline",
    "purpose": "purpose",
    "name": "name",
    "phone": "phone",
}


def norm(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_greeting(text):
    t = norm(text)
    return t in {
        "hi", "hello", "hey", "hii", "hiii", "helo",
        "good morning", "good afternoon", "good evening", "namaste",
        "hi there", "hello there",
    }


def flexible_answer(text, field):
    t = norm(text)
    if field == "budget":
        return any(p in t for p in [
            "budget no issue", "budget is no issue", "no budget", "any budget",
            "budget doesnt matter", "budget doesn't matter", "money no issue",
            "price no issue", "no problem with budget", "flexible budget",
            "budget flexible", "budget is flexible", "any price", "whatever budget",
        ])
    if field == "area":
        return any(p in t for p in [
            "any area", "anywhere", "no area preference", "area no issue",
            "location no issue", "any location", "location flexible",
            "area flexible", "any locality",
        ])
    if field == "possession":
        return any(p in t for p in [
            "either", "no preference", "anything is fine", "doesn't matter",
            "doesnt matter", "any is fine",
        ])
    if field == "timeline":
        return any(p in t for p in [
            "no hurry", "not decided", "flexible", "anytime", "no fixed timeline",
            "no timeline",
        ])
    return False


def extract(text):
    """Extract facts from a natural-language buyer message."""
    raw = text or ""
    x = norm(raw)
    d = {}

    # Property type — including common natural variants.
    if re.search(r"\b(?:empty\s+|open\s+)?plot\b", x):
        d["property_type"] = "Plot"
    elif "commercial" in x or "shop" in x or "office space" in x:
        d["property_type"] = "Commercial"
    elif re.search(r"\b(?:2|two)\s*(?:or|/|-|to|and)\s*(?:3|three)\s*bhk\b", x):
        d["property_type"] = "2 or 3 BHK"
    else:
        m = re.search(r"\b([1-5])\s*bhk\b", x)
        if m:
            d["property_type"] = f"{m.group(1)} BHK"

    # Budget: 50 lakh, 50 lac, ₹50L, 1.2 crore, etc.
    if flexible_answer(x, "budget"):
        d["budget"] = "Flexible / no budget limit"
    else:
        m = re.search(
            r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*"
            r"(lakh|lac|lakhs|crore|cr|l)\b", x
        )
        if m:
            unit = m.group(2)
            if unit == "l":
                unit = "lakh"
            d["budget"] = f"₹{m.group(1)} {unit}"

    # Area — first handle common localities, then generic 'in/near/at ...'.
    known = [
        "nanded railway station", "nanded station", "cidco nanded", "cidco",
        "vazirabad", "taroda", "shivaji nagar", "airport road", "miyapur",
        "hafeezpet", "kukatpally", "nanded", "hyderabad",
    ]
    found = [a for a in known if a in x]
    if found:
        chosen = []
        for a in sorted(found, key=len, reverse=True):
            if not any(a in c or c in a for c in chosen):
                chosen.append(a)
        d["area"] = ", ".join(a.title() for a in reversed(chosen))
    elif not flexible_answer(x, "area"):
        m = re.search(r"\b(?:in|near|at|around)\s+([a-z][a-z .'-]{2,40}?)(?:\s+(?:for|with|under|within|around)\b|[,.!?]|$)", raw, re.I)
        if m:
            candidate = re.sub(r"\s+", " ", m.group(1)).strip(" .,-")
            if candidate and candidate.lower() not in {"a", "an", "the"}:
                d["area"] = candidate.title()
    if flexible_answer(x, "area"):
        d["area"] = "Flexible / any area"

    # Possession is irrelevant for a plot, but can still be stored if explicitly stated.
    if any(p in x for p in [
        "ready for move", "ready to move", "ready possession",
        "ready for possession", "immediate possession",
    ]):
        d["possession"] = "Ready to move"
    elif "under construction" in x:
        d["possession"] = "Under construction"
    elif flexible_answer(x, "possession"):
        d["possession"] = "No preference"

    # Timeline.
    if any(p in x for p in [
        "within 1 month", "this month", "next month", "urgent", "immediately", "immediate",
    ]):
        d["timeline"] = "Within 1 month"
    elif re.search(r"\b[12]\s*(?:-|–|to)\s*3\s*months?\b", x):
        d["timeline"] = "1–3 months"
    elif re.search(r"\b3\s*(?:-|–|to)\s*6\s*months?\b", x) or "within 6 months" in x:
        d["timeline"] = "3–6 months"
    elif flexible_answer(x, "timeline"):
        d["timeline"] = "Flexible"

    # Plot size.
    m = re.search(
        r"\b([0-9]+(?:\.[0-9]+)?)\s*(sq\.?\s*ft|sqft|square feet|sq\.?\s*yd|square yards|guntha|acre|acres)\b",
        x,
    )
    if m:
        d["plot_size"] = f"{m.group(1)} {m.group(2)}"

    if any(p in x for p in ["investment", "investing"]):
        d["purpose"] = "Investment"
    elif any(p in x for p in ["self use", "self-use", "own use", "for living", "to live"]):
        d["purpose"] = "Self-use"

    m = re.search(r"\b(?:my name is|i am|i'm|im)\s+([a-zA-Z][a-zA-Z ]{1,30})\b", raw, re.I)
    if m:
        d["name"] = m.group(1).strip().title()

    m = re.search(r"\b(?:\+91[\s-]?)?([6-9]\d{9})\b", x)
    if m:
        d["phone"] = m.group(1)

    return d


def merge(memory, facts):
    out = dict(memory or {})
    for k, v in (facts or {}).items():
        if v:
            out[k] = v
    return out


def required_fields(memory):
    p = norm(memory.get("property_type", ""))
    if "plot" in p:
        return ["property_type", "area", "budget", "plot_size", "timeline"]
    if "commercial" in p:
        return ["property_type", "area", "budget", "possession", "timeline"]
    return ["property_type", "area", "budget", "possession", "timeline"]


def next_missing(memory):
    for field in required_fields(memory):
        if not memory.get(field):
            return field
    return None


def score(memory):
    req = required_fields(memory)
    supplied = sum(bool(memory.get(f)) for f in req)
    s = int(10 + 70 * supplied / len(req))
    if memory.get("timeline") == "Within 1 month":
        s += 15
    if memory.get("phone"):
        s += 5
    return min(s, 100)


def status(s):
    return "🔥 HOT" if s >= 80 else ("🟠 WARM" if s >= 55 else "⚪ COLD")


def local_reply(user_text, memory):
    """Deterministic fallback designed to avoid repeated questions."""
    if is_greeting(user_text):
        return "Hi! 👋 Welcome. I can help you find a suitable property. What are you looking for?"

    missing = next_missing(memory)
    if missing == "property_type":
        return "Sure 👍 What are you looking for — a 2/3 BHK, plot, commercial property, or something else?"
    if missing == "area":
        return "Great 👍 Which area or locality would you prefer? You can also say 'any area'."
    if missing == "budget":
        return "Got it 👍 What's your approximate budget? If budget isn't an issue, just tell me and I'll keep it flexible."
    if missing == "possession":
        return "And do you prefer ready-to-move or under-construction? You can also say no preference."
    if missing == "plot_size":
        return "Got it — an empty plot. 👍 Roughly what plot size are you looking for? For example, 1,000 sq ft or 2 guntha."
    if missing == "timeline":
        return "When are you planning to purchase — soon, within a few months, or are you flexible?"

    summary = ", ".join(
        f"{FIELD_LABELS.get(k, k)}: {v}"
        for k, v in memory.items()
        if v and k not in {"name", "phone"}
    )
    return f"Perfect 👍 I have everything I need: {summary}. Would you like to arrange a call or property visit?"
