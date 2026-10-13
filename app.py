"""Local educational care-navigation prototype. Never logs intake requests."""
import copy
import hashlib
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
LOCK = threading.RLock()
SAFETY_NOTICE = "This educational prototype cannot assess or rule out an emergency. If you think this is an emergency, call 911. Do not delay care to research insurance."
# Illustrative detection only: deliberately not a validated clinical triage protocol.
ALERT_PATTERN = re.compile(r"chest pain|can't breathe|cannot breathe|difficulty breathing|severe bleeding|stroke|suicid|overdose", re.I)
SAFETY_HASH = hashlib.sha256((SAFETY_NOTICE + ALERT_PATTERN.pattern).encode()).hexdigest()
BASE_POLICY = {"ask_language": False, "ask_travel": False, "ask_service": False}
RESOURCES = [
    {"id": "hrsa", "name": "HRSA Find a Health Center", "kind": "Care directory", "url": "https://findahealthcenter.hrsa.gov/", "description": "Search health centers near your ZIP code. Ask the center about services, sliding-fee discounts, and appointments."},
    {"id": "dhs", "name": "LA County Health Services financial assistance", "kind": "Financial assistance — not insurance", "url": "https://dhs.lacounty.gov/patient-information/get-coverage/financial-services/", "description": "Learn about help paying for eligible care at LA Health Services, including the Ability to Pay program. Ask staff about current requirements."},
    {"id": "benefits", "name": "BenefitsCal", "kind": "Public benefits application", "url": "https://benefitscal.com/", "description": "Official California application portal for benefits including Medi-Cal. Eligibility is determined by the administering agency."},
    {"id": "covered", "name": "Covered California", "kind": "Health insurance marketplace", "url": "https://www.coveredca.com/", "description": "Use official plan comparison and enrollment assistance. Eligibility, enrollment windows, subsidies, and prices require current official checks."},
]
CLINICS = [
    {"name": "Hubert H. Humphrey Comprehensive Health Center", "services": ["primary care", "urgent care", "dental", "behavioral health"], "zip": "90003", "address": "5850 S. Main St., Los Angeles, CA 90003", "website": "https://dhs.lacounty.gov/health-centers/home/humphrey/", "payment": "LA County system; ask about financial assistance and current coverage options.", "languages": "Ask clinic", "source": "LA Health Services"},
    {"name": "H. Claude Hudson Comprehensive Health Center", "services": ["primary care", "women's health", "specialty referrals"], "zip": "90007", "address": "2829 S. Grand Ave., Los Angeles, CA 90007", "website": "https://dhs.lacounty.gov/our-locations/", "payment": "LA County system; ask about financial assistance and current coverage options.", "languages": "Ask clinic", "source": "LA Health Services"},
    {"name": "Angeles Community Health Center", "services": ["primary care", "dental", "behavioral health"], "zip": "90057", "address": "1919 W 7th St., Los Angeles, CA 90057", "website": "https://www.angelescommunity.org/", "payment": "FQHC; sliding fee may be available for eligible patients.", "languages": "Ask clinic", "source": "Angeles Community Health Center"},
    {"name": "Saban Community Clinic – Beverly Health Center", "services": ["primary care", "dental", "behavioral health"], "zip": "90048", "address": "8405 Beverly Blvd., Los Angeles, CA 90048", "website": "https://www.sabancommunityclinic.org/", "payment": "Community clinic; ask about self-pay and sliding-fee options.", "languages": "Ask clinic", "source": "Saban Community Clinic"},
    {"name": "Saban Community Clinic – Hollywood Health Center", "services": ["primary care", "dental", "behavioral health"], "zip": "90028", "address": "6043 Hollywood Blvd., Los Angeles, CA 90028", "website": "https://www.sabancommunityclinic.org/", "payment": "Community clinic; ask about self-pay and sliding-fee options.", "languages": "Ask clinic", "source": "Saban Community Clinic"},
    {"name": "St. John’s Community Health", "services": ["primary care", "dental", "behavioral health", "women's health"], "zip": "90037", "address": "808 W. 58th St., Los Angeles, CA 90037", "website": "https://www.sjch.org/", "payment": "Community health center; ask about coverage, self-pay, and assistance options.", "languages": "Ask clinic", "source": "St. John’s Community Health"},
    {"name": "Kheir Clinic", "services": ["primary care", "dental", "behavioral health", "women's health"], "zip": "90010", "address": "Los Angeles / Koreatown network", "website": "https://lakheir.org/", "payment": "Low-cost and community clinic services; ask about fees and eligibility.", "languages": "Ask clinic", "source": "Kheir Clinic"},
    {"name": "Universal Community Health Center – O'Neill", "services": ["primary care", "dental", "behavioral health"], "zip": "90011", "address": "1919 S. San Pedro St., Los Angeles, CA 90011", "website": "https://uchcla.org/", "payment": "Community clinic; ask about self-pay and support options.", "languages": "Ask clinic", "source": "Universal Community Health Center"},
    {"name": "Via Care Community Health Center – 507 Health Center", "services": ["primary care", "dental", "behavioral health", "women's health"], "zip": "90022", "address": "507 S. Atlantic Blvd., Los Angeles, CA 90022", "website": "https://www.viacarela.org/", "payment": "Community clinic; ask about self-pay and sliding-fee options.", "languages": "Ask clinic", "source": "Via Care Community Health Center"},
    {"name": "Via Care Community Health Center – Cesar Chavez Health Center", "services": ["primary care", "dental", "behavioral health", "women's health"], "zip": "90022", "address": "4755 E. Cesar E Chavez Ave., Los Angeles, CA 90022", "website": "https://www.viacarela.org/", "payment": "Community clinic; ask about self-pay and sliding-fee options.", "languages": "Ask clinic", "source": "Via Care Community Health Center"},
    {"name": "Comprehensive Community Health Centers – Eagle Rock", "services": ["primary care", "dental", "behavioral health"], "zip": "90041", "address": "1704 Colorado Blvd., Los Angeles, CA 90041", "website": "https://cchccenters.org/", "payment": "FQHC/community clinic; ask about coverage and self-pay options.", "languages": "Multilingual site; ask clinic", "source": "Comprehensive Community Health Centers"},
]
GUIDANCE_RULES = [
    {
        "pattern": re.compile(r"headache|migraine", re.I),
        "label": "Headache symptoms",
        "care_level": "Primary care or urgent care depending on severity",
        "doctor_types": ["Primary care clinician", "Urgent care clinician", "Neurology if symptoms are recurrent or clinician-directed"],
        "possible_causes": ["Common possibilities include tension headache, migraine, dehydration, poor sleep, or a viral illness."],
        "self_care": ["Rest, hydrate, and limit anything that seems to worsen the headache.", "Seek urgent care sooner if the headache is suddenly severe, follows an injury, or comes with weakness, confusion, fever, or neck stiffness."],
        "care_options": ["Primary care or urgent care may be appropriate depending on severity and how long it has lasted."]
    },
    {
        "pattern": re.compile(r"cough|fever|sore throat|congestion|runny nose|cold|flu", re.I),
        "label": "Cold or flu-like symptoms",
        "care_level": "Primary care, urgent care, or telehealth",
        "doctor_types": ["Primary care clinician", "Urgent care clinician", "Telehealth clinician"],
        "possible_causes": ["Common possibilities include a viral upper respiratory infection, flu, COVID-19, allergies, or throat irritation."],
        "self_care": ["Rest, fluids, and monitoring worsening symptoms are common first steps.", "Seek prompt care if breathing becomes difficult, symptoms are rapidly worsening, or fever is persistent."],
        "care_options": ["Primary care, urgent care, or telehealth may help with testing and next-step advice."]
    },
    {
        "pattern": re.compile(r"stomach|abdominal|nausea|vomit|diarrhea|constipation", re.I),
        "label": "Digestive symptoms",
        "care_level": "Primary care or urgent care depending on severity",
        "doctor_types": ["Primary care clinician", "Urgent care clinician", "Gastroenterology if clinician-directed"],
        "possible_causes": ["Common possibilities include a stomach bug, food-related irritation, constipation, reflux, or other digestive issues."],
        "self_care": ["Hydration and simple foods may help while you monitor symptoms.", "Seek prompt care if pain is severe, you cannot keep fluids down, stool is black or bloody, or symptoms keep worsening."],
        "care_options": ["Primary care or urgent care may be useful depending on severity and duration."]
    },
    {
        "pattern": re.compile(r"rash|itch|hives|skin", re.I),
        "label": "Skin symptoms",
        "care_level": "Primary care or dermatology; urgent care if rapidly worsening",
        "doctor_types": ["Primary care clinician", "Dermatologist", "Urgent care clinician"],
        "possible_causes": ["Common possibilities include irritation, allergy, eczema, infection, insect bites, or other skin conditions."],
        "self_care": ["Avoid new products or triggers if one seems likely.", "Seek prompt care if the rash is spreading quickly, involves facial swelling, or comes with fever or breathing symptoms."],
        "care_options": ["Primary care, dermatology, or urgent care may be appropriate depending on severity."],
    },
    {
        "pattern": re.compile(r"tooth|teeth|dental|gum|mouth pain", re.I),
        "label": "Dental symptoms",
        "care_level": "Dental care soon; urgent care if swelling or fever develops",
        "doctor_types": ["Dentist", "Dental clinic", "Urgent care clinician if severe and dental care is not available"],
        "possible_causes": ["Common possibilities include tooth decay, gum irritation, a cracked tooth, or infection."],
        "self_care": ["Avoid anything that clearly worsens the pain, such as very hot, cold, or hard foods.", "Seek urgent dental or medical care if swelling is spreading, fever develops, or swallowing becomes difficult."],
        "care_options": ["Dental care is usually the most relevant next step; urgent care may help if symptoms are severe and dental care is not immediately available."],
    },
    {
        "pattern": re.compile(r"anxiety|panic|stress|depress|sad|therapy|mental health", re.I),
        "label": "Mental health concerns",
        "care_level": "Mental health support or primary care; urgent help if safety is a concern",
        "doctor_types": ["Mental health professional", "Primary care clinician", "Crisis support services if urgent"],
        "possible_causes": ["Stress, anxiety, depression, trauma, burnout, or other mental health conditions can contribute to these concerns."],
        "self_care": ["Consider reaching out to a trusted person and making a plan for support today.", "Seek urgent help now if you feel unsafe, think you may act on self-harm thoughts, or cannot care for yourself."],
        "care_options": ["Primary care or a mental health professional may be appropriate starting points for ongoing support."],
    },
]


def initial_state():
    return {"version": 1, "policy": BASE_POLICY.copy(), "history": [], "pending": None}


def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else initial_state()


def save_state(state):
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2))
    temporary.replace(STATE_PATH)


def build_recommendations(data):
    symptoms = str(data.get("symptoms", ""))[:2000]
    service = str(data.get("service", ""))[:200]
    text = f"{symptoms} {service}".strip()
    if not text:
        return {
            "summary": "Add a symptom or care goal to receive general, non-diagnostic suggestions.",
            "care_level": "Primary care is often a reasonable starting point for non-emergency concerns.",
            "doctor_types": ["Primary care clinician"],
            "possible_causes": [],
            "self_care": [],
            "care_options": ["If you are unsure where to start, primary care is often a reasonable first stop for non-emergency concerns."],
            "matched_topics": [],
        }
    matched = [rule for rule in GUIDANCE_RULES if rule["pattern"].search(text)]
    if not matched:
        return {
            "summary": "No specific guidance topic matched your wording, so the safest next step is general care navigation rather than guessing a cause.",
            "care_level": "Primary care is often the best general starting point; urgent care may fit if the concern is worsening or cannot wait.",
            "doctor_types": ["Primary care clinician", "Urgent care clinician if symptoms are worsening"],
            "possible_causes": ["Many symptoms can have several causes, and this prototype cannot narrow them down reliably."],
            "self_care": ["Track when the concern started, what makes it better or worse, and any new symptoms before contacting care."],
            "care_options": ["Primary care is often the best general starting point for non-emergency concerns; urgent care may be more appropriate if the problem is getting worse or cannot wait."],
            "matched_topics": [],
        }
    possible_causes, self_care, care_options, doctor_types = [], [], [], []
    for rule in matched[:2]:
        possible_causes.extend(rule["possible_causes"])
        self_care.extend(rule["self_care"])
        care_options.extend(rule["care_options"])
        doctor_types.extend(rule["doctor_types"])
    return {
        "summary": "Based on the words you entered, these are general possibilities and next-step suggestions to discuss with a clinician. They are not a diagnosis.",
        "care_level": matched[0]["care_level"],
        "doctor_types": list(dict.fromkeys(doctor_types)),
        "possible_causes": possible_causes,
        "self_care": self_care,
        "care_options": care_options,
        "matched_topics": [rule["label"] for rule in matched[:2]],
    }


def build_provider_matches(data, recommendations):
    zip_code = str(data.get("zip", "")).strip() or "your ZIP code"
    language = str(data.get("language", "")).strip()
    insurance = data.get("insurance") or "unspecified"
    service = str(data.get("service", "")).strip().lower()
    matched_topics = " ".join(recommendations.get("matched_topics", []))
    doctor_text = " ".join(recommendations.get("doctor_types", []))
    text = f"{service} {matched_topics} {doctor_text}".lower()
    specialty = "Primary care"
    if "dent" in text or "tooth" in text:
        specialty = "Dental care"
    elif "skin" in text or "dermat" in text or "rash" in text:
        specialty = "Dermatology or primary care"
    elif "mental" in text or "therapy" in text or "anxiety" in text:
        specialty = "Mental health services"
    elif "urgent" in recommendations.get("care_level", "").lower():
        specialty = "Urgent care"
    support = f"Language support: {language}" if language else "Language support: ask clinic"
    insurance_line = {
        "insured": "Insurance: verify your exact plan network with the clinic and insurer.",
        "uninsured": "Payment: ask about self-pay rates and sliding-fee options.",
        "unsure": "Coverage: confirm whether the clinic can help review your insurance status or self-pay options.",
    }.get(insurance, "Coverage: verify insurance or self-pay options directly with the clinic.")
    try:
        zip_prefix = int(zip_code[:3]) if zip_code.isdigit() else None
    except ValueError:
        zip_prefix = None
    desired = set()
    if "dental" in specialty.lower() or "dent" in text or "tooth" in text:
        desired.add("dental")
    if "mental" in specialty.lower() or any(term in text for term in ("mental", "therapy", "anxiety", "stress", "depress")):
        desired.add("behavioral health")
    if not desired:
        desired.add("primary care")
    scored = []
    for clinic in CLINICS:
        score = 0
        if any(service_name in clinic["services"] for service_name in desired):
            score += 3
        if "urgent care" in clinic["services"] and "urgent" in recommendations.get("care_level", "").lower():
            score += 2
        if zip_prefix and clinic["zip"].isdigit() and abs(int(clinic["zip"][:3]) - zip_prefix) <= 1:
            score += 2
        elif zip_code and clinic["zip"] == zip_code:
            score += 3
        if insurance == "uninsured" and any(term in clinic["payment"].lower() for term in ("sliding", "self-pay", "financial assistance", "community", "fqhc")):
            score += 2
        scored.append((score, clinic))
    cards = []
    for _, clinic in sorted(scored, key=lambda item: (-item[0], item[1]["name"]))[:4]:
        cards.append({
            "title": clinic["name"],
            "address": clinic["address"],
            "website": clinic["website"],
            "details": [
                f"Services: {', '.join(clinic['services'])}",
                clinic["payment"],
                support,
                "Insurance acceptance and appointment availability are unverified; call the clinic directly.",
            ],
            "source": clinic["source"],
        })
    return {
        "summary": f"Start by looking for {specialty.lower()} near {zip_code}.",
        "cards": cards,
    }


def build_affordability_section(data):
    insurance = data.get("insurance") or "unspecified"
    if insurance == "insured":
        return {
            "summary": "Start with your plan network, then compare costs before booking.",
            "items": [
                "Use your insurer's directory, then confirm the exact plan network with the clinic.",
                "Ask about copays, deductibles, and whether labs or imaging would be billed separately.",
                "Keep self-pay or community-clinic options in mind if the in-network wait is too long.",
            ],
        }
    if insurance == "uninsured":
        return {
            "summary": "Lower-cost care and public enrollment help should be part of your next step.",
            "items": [
                "Check sliding-fee community clinics and LA County financial assistance options first.",
                "Use BenefitsCal and Covered California to explore whether you qualify for coverage help.",
                "Ask clinics for self-pay rates before booking and whether payment plans are available.",
            ],
        }
    return {
        "summary": "Clarify your coverage status while keeping low-cost care options available.",
        "items": [
            "Ask clinics whether they can help confirm insurance, self-pay, or sliding-fee options.",
            "Review BenefitsCal and Covered California to understand possible coverage pathways.",
            "Compare community-clinic and urgent care self-pay pricing if you need a fast appointment.",
        ],
    }


def build_free_resources(data):
    service = str(data.get("service", "")).strip().lower()
    symptoms = str(data.get("symptoms", "")).strip().lower()
    text = f"{service} {symptoms}"
    resources = [
        "Community health centers and FQHCs that may offer sliding-fee or low-cost care.",
        "LA County financial assistance and enrollment help for people with limited or no coverage.",
    ]
    if any(term in text for term in ("dent", "tooth", "gum")):
        resources.append("Low-cost dental clinics or dental-school clinics in your area.")
    if any(term in text for term in ("anxiety", "mental", "stress", "depress", "panic")):
        resources.append("Mental health support lines and county/community behavioral health resources.")
    resources.append("Transportation or public-benefit support lines if getting to care is difficult.")
    return {
        "summary": "These free or lower-cost resources are worth checking while you arrange care.",
        "items": resources,
    }


def navigate(data, policy):
    symptoms = str(data.get("symptoms", ""))[:2000]
    urgent = bool(ALERT_PATTERN.search(symptoms))
    if urgent:
        return {"notice": SAFETY_NOTICE, "urgent": True, "message": "Your description includes a phrase that may indicate an emergency. Call 911 if these symptoms are happening now or you may be in danger. This simple text check can be wrong; do not rely on it to decide whether you are safe.", "questions": [], "resources": [], "unknowns": ["This is not a diagnosis or a validated triage assessment."]}
    questions = []
    for key, label in [("zip", "What is your LA County ZIP code?"), ("insurance", "Do you have insurance, no insurance, or are you unsure?")]:
        if not data.get(key):
            questions.append({"field": key, "text": label})
    for rule, key, label in [("ask_language", "language", "What language would you prefer for care?"), ("ask_travel", "travel", "How far can you travel, and do you have transport constraints?"), ("ask_service", "service", "What type of care are you looking for? If unsure, say unsure.")]:
        if policy[rule] and not data.get(key):
            questions.append({"field": key, "text": label})
    insured = data.get("insurance") == "insured"
    resources = [r.copy() for r in RESOURCES if not insured or r["id"] in ("hrsa", "dhs")]
    recommendations = build_recommendations(data)
    providers = build_provider_matches(data, recommendations)
    affordability = build_affordability_section(data)
    free_resources = build_free_resources(data)
    steps = ["Use the care directory to search your ZIP code; this app has not searched or confirmed individual clinics.", "Contact the clinic to confirm the service, language support, new-patient status, fees, and appointment times."]
    if insured:
        steps.insert(0, "Use your insurer's directory, then verify the exact plan network with both the insurer and clinic.")
    else:
        steps.append("Use official enrollment help to explore coverage; ask clinics about lower-cost care while you explore options.")
    return {"notice": SAFETY_NOTICE, "urgent": False, "message": "Here are starting points for finding care and payment help—not a diagnosis or eligibility decision.", "questions": questions, "resources": resources, "recommendations": recommendations, "providers": providers, "affordability": affordability, "free_resources": free_resources, "steps": steps, "unknowns": ["Recommendations are based on simple keyword matching and may miss important context.", "No live clinic search, appointment availability, network status, or price has been verified.", "Resource links are a manually curated seed list; current program rules must be checked on the official sites.", "No alert from the text check does not mean your symptoms are safe."], "preferences": {k: data.get(k, "") for k in ("zip", "language", "travel", "service")}}


# The proposer sees development failures only. Holdout cases are evaluated separately.
DEVELOPMENT = [
    {"name": "Language preference missing", "data": {"zip": "90012", "insurance": "uninsured"}, "required": ["language"]},
    {"name": "Transport preference missing", "data": {"zip": "90022", "insurance": "uninsured", "language": "Spanish"}, "required": ["travel"]},
    {"name": "Care type missing", "data": {"zip": "90033", "insurance": "insured", "travel": "5 miles"}, "required": ["service"]},
]
HOLDOUT = [
    {"name": "Uninsured care seeker", "data": {"zip": "90011", "insurance": "uninsured"}, "required": ["language", "travel", "service"]},
    {"name": "Insured care seeker", "data": {"zip": "90045", "insurance": "insured", "language": "English"}, "required": ["travel", "service"]},
    {"name": "Already supplied preferences", "data": {"zip": "90026", "insurance": "unsure", "language": "Spanish", "travel": "bus only", "service": "primary care"}, "required": []},
]


def evaluate(policy, cases):
    results = []
    for case in cases:
        result = navigate(case["data"], policy)
        asked = {q["field"] for q in result["questions"]}
        missing = sorted(set(case["required"]) - asked)
        repeats = sorted(k for k in asked if case["data"].get(k))
        results.append({"name": case["name"], "passed": not missing and not repeats, "missing": missing, "repeated": repeats})
    return {"passed": sum(r["passed"] for r in results), "total": len(results), "results": results}


def safety_tests(policy):
    checks = []
    for phrase in ("chest pain", "I cannot breathe", "severe bleeding", "suicidal thoughts", "possible overdose"):
        output = navigate({"symptoms": phrase, "insurance": "uninsured"}, policy)
        checks.append({"name": f"Escalation: {phrase}", "passed": output["urgent"] and not output["resources"] and not output["questions"]})
    normal = navigate({}, policy)
    checks.append({"name": "Safety disclaimer always present", "passed": normal["notice"] == SAFETY_NOTICE})
    checks.append({"name": "Unverified availability labeled", "passed": any("No live clinic search" in item for item in normal["unknowns"])})
    return {"passed": sum(c["passed"] for c in checks), "total": len(checks), "results": checks, "scope": "Illustrative regression checks, not clinical validation."}


def propose(state):
    before = evaluate(state["policy"], DEVELOPMENT)
    missing = {field for r in before["results"] for field in r["missing"]}
    mapping = {"language": "ask_language", "travel": "ask_travel", "service": "ask_service"}
    target = next((field for field in mapping if field in missing), None)
    if not target:
        return {"done": True, "message": "No more supported patches. This bounded rule-based proposer has exhausted its three changes; it cannot invent new capabilities."}
    candidate = copy.deepcopy(state["policy"])
    rule = mapping[target]
    candidate[rule] = True
    after = evaluate(candidate, DEVELOPMENT)
    held_before = evaluate(state["policy"], HOLDOUT)
    held_after = evaluate(candidate, HOLDOUT)
    safety = safety_tests(candidate)
    eligible = (after["passed"] > before["passed"] and held_after["passed"] >= held_before["passed"] and safety["passed"] == safety["total"])
    return {"done": False, "base_version": state["version"], "change": {"key": rule, "before": False, "after": True}, "reason": f"Development scenarios missed the {target} preference. Ask only when not already supplied.", "candidate": candidate, "development_before": before, "development_after": after, "holdout_before": held_before, "holdout_after": held_after, "safety": safety, "safety_hash": SAFETY_HASH, "eligible": eligible}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not store URLs or patient data in request logs.

    def respond(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            with LOCK:
                state = load_state()
                self.respond({**state, "development": evaluate(state["policy"], DEVELOPMENT), "holdout": evaluate(state["policy"], HOLDOUT), "safety": safety_tests(state["policy"]), "safety_hash": SAFETY_HASH})
            return
        files = {"/": ("index.html", "text/html"), "/rsi": ("rsi.html", "text/html"), "/style.css": ("style.css", "text/css"), "/main.js": ("main.js", "text/javascript"), "/rsi.js": ("rsi.js", "text/javascript")}
        if path not in files:
            self.respond({"error": "Not found"}, 404)
            return
        filename, mime = files[path]
        body = (ROOT / "static" / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Allow same-site proxy/browser requests while rejecting obviously foreign origins.
        origin = self.headers.get("Origin")
        if origin:
            parsed_origin = urlparse(origin)
            host = self.headers.get("Host", "")
            if parsed_origin.scheme not in ("http", "https"):
                self.respond({"error": "Cross-origin request rejected"}, 403)
                return
            same_host = parsed_origin.netloc == host
            trusted_proxy = parsed_origin.netloc.endswith("ide.grailai.io")
            localhost_origin = parsed_origin.hostname in ("127.0.0.1", "localhost")
            if not (same_host or trusted_proxy or localhost_origin):
                self.respond({"error": "Cross-origin request rejected"}, 403)
                return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 12000:
                self.respond({"error": "Request too large"}, 413)
                return
            data = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Expected object")
            with LOCK:
                state = load_state()
                path = urlparse(self.path).path
                if path == "/api/navigate":
                    result = navigate(data, state["policy"])
                    result["version"] = state["version"]
                    self.respond(result)
                elif path == "/api/propose":
                    state["pending"] = propose(state)
                    save_state(state)
                    self.respond(state["pending"])
                elif path == "/api/approve":
                    patch = state["pending"]
                    if not patch or patch.get("done") or not patch["eligible"] or patch["base_version"] != state["version"] or patch["safety_hash"] != SAFETY_HASH:
                        self.respond({"error": "No eligible patch to approve"}, 409)
                        return
                    state["policy"] = patch["candidate"]
                    state["version"] += 1
                    state["history"].append({"version": state["version"], "change": patch["change"], "reason": patch["reason"], "approved_by": "local demo operator", "development_passed": patch["development_after"]["passed"], "holdout_passed": patch["holdout_after"]["passed"]})
                    state["pending"] = None
                    save_state(state)
                    self.respond({"version": state["version"]})
                elif path == "/api/reject":
                    state["pending"] = None
                    save_state(state)
                    self.respond({"rejected": True})
                else:
                    self.respond({"error": "Not found"}, 404)
        except (ValueError, TypeError):
            self.respond({"error": "Invalid request"}, 400)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"LA Care Navigator: http://localhost:{args.port} (local educational demo)")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
