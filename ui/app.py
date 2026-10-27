"""MedLabel Assist: chat interface (Streamlit). Talks to the FastAPI service over HTTP.

Run the API first (uvicorn api:app --app-dir src), then:  streamlit run ui/app.py
Security note: hiding views by role here is cosmetic. The API enforces roles on every request.
The word-by-word reveal of an answer is a display effect only; the full answer has already
been produced and verified by the API before it is shown.
"""
import base64
import html
import json
import os
import re
import time
import uuid

import requests
import streamlit as st

DEFAULT_API = os.environ.get("MEDLABEL_API", "http://127.0.0.1:8000")

SUGGESTIONS = [
    ("Dosage", "How is the daily amount of terazosin usually decided?"),
    ("Warnings", "In which patients is clindamycin unsafe?"),
    ("Overdose", "What are the signs of too much ivermectin and what should the doctor do?"),
    ("Out of scope", "What is the price of metformin at pharmacies in Hyderabad?"),
]

REASONS = {
    "low retrieval score": "The label text I have does not contain enough relevant evidence for this question.",
    "no recognized drug": "I could not identify a drug from the labels in this dataset. Please name the drug.",
    "model abstained": "The retrieved label text does not answer this question.",
    "blocked: prompt injection": "This looks like an attempt to change my instructions, so I did not process it.",
    "evidence removed by guardrail": "The retrieved text was removed by a safety check, so there is nothing safe to answer from.",
}

st.set_page_config(page_title="MedLabel Assist", page_icon=":material/medication:", layout="centered")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:wght@400;500;600&display=swap');
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"] p, [data-testid="stTextInputField"], textarea, button p,
[data-testid="stExpander"] summary p, [data-testid="stMetric"] div { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3, .serif { font-family: 'Source Serif 4', Georgia, serif !important; font-weight: 500 !important; letter-spacing: -0.01em; }
[data-testid="stDecoration"], #MainMenu, footer { display: none; }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 780px; padding-top: 2.4rem; padding-bottom: 8rem; }

/* sidebar */
[data-testid="stSidebar"] { border-right: 1px solid #E8E5DA; }
[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
[data-testid="stSidebar"] [data-testid="stButton"] { width: 100%; }
[data-testid="stSidebar"] button { width: 100%; justify-content: flex-start; text-align: left; border-radius: 10px; }
[data-testid="stSidebar"] button p { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.brand { display: flex; align-items: center; gap: .6rem; font-family: 'Source Serif 4', Georgia, serif; font-size: 1.25rem; font-weight: 500; margin-bottom: 1rem; }
.mark { display: inline-flex; align-items: center; justify-content: center; width: 1.9rem; height: 1.9rem; border-radius: 9px; background: #2F6F62; color: #fff; font-family: 'Inter', sans-serif; font-weight: 600; font-size: .95rem; }
.side-label { color: #8A867A; font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; margin: 1.2rem 0 .55rem .2rem; }

/* chat messages */
[data-testid="stChatMessage"] { background: transparent; padding: .5rem 0; gap: .8rem; }
[data-testid="stChatMessage"]:has([aria-label*="from user"]) { background: #F0EEE6; border: 1px solid #E8E5DA; border-radius: 16px; padding: .75rem 1rem; }
[data-testid="stChatMessageAvatarCustom"] { background: #DDD9CB; border-radius: 9px; }
[data-testid="stChatMessage"]:has([aria-label*="from assistant"]) [data-testid="stChatMessageAvatarCustom"] { background: #2F6F62; }
[data-testid="stChatMessage"]:has([aria-label*="from assistant"]) [data-testid="stIconMaterial"] { color: #FFFFFF !important; }
[data-testid="stChatMessage"] p { line-height: 1.65; font-size: 1.0rem; }

/* chat input */
[data-testid="stChatInput"] { border-radius: 20px; border: 1px solid #D9D5C8; box-shadow: 0 2px 10px rgba(60, 55, 40, .07); }
[data-testid="stChatInput"], [data-testid="stChatInput"] div { background-color: #FFFFFF; }
[data-testid="stChatInput"] textarea { background: transparent; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: #FAF9F5; }

/* answer pieces */
sup.cite { color: #2F6F62; font-weight: 600; font-size: .72em; padding: 0 1px; }
.chip { display: inline-block; padding: .12rem .65rem; border-radius: 999px; font-size: .74rem; font-weight: 500; margin-bottom: .55rem; }
.chip.ok { background: #E3EFEA; color: #1E5448; }
.chip.no { background: #F6EBD3; color: #7A5A12; }
.decline { background: #FBF4E6; border: 1px solid #F0E0BB; border-radius: 14px; padding: .9rem 1.1rem; color: #5B4A1E; line-height: 1.55; }
.decline b { display: block; margin-bottom: .2rem; }
.src-label { color: #8A867A; font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; margin: 1rem 0 .3rem; }
.meta { color: #8A867A; font-size: .76rem; margin-top: .7rem; }
.excerpt { border-left: 3px solid #D9D5C8; padding-left: .8rem; margin-bottom: .7rem; color: #4A483F; font-size: .92rem; line-height: 1.6; }
[data-testid="stExpander"], [data-testid="stExpander"] details, [data-testid="stExpander"] summary { background-color: #FFFFFF !important; }
[data-testid="stCaptionContainer"] { font-size: .8rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .35rem; }
[data-testid="stExpander"] { border: 1px solid #E8E5DA; border-radius: 12px; }
[data-testid="stExpander"] summary { font-size: .9rem; }

/* welcome screen */
.hero { font-family: 'Source Serif 4', Georgia, serif; font-size: 2.5rem; font-weight: 500; margin: 3rem 0 .3rem; letter-spacing: -0.02em; }
.hero-sub { color: #6B675B; font-size: 1.05rem; margin-bottom: 2rem; line-height: 1.55; }
.tag { color: #2F6F62; font-size: .72rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; margin: .6rem 0 .25rem .2rem; }
[data-testid="stMainBlockContainer"] [data-testid="stButton"], [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has([data-testid="stButton"]) { width: 100% !important; }
[data-testid="stMainBlockContainer"] [data-testid="stButton"] button { width: 100%; text-align: left; justify-content: flex-start; border-radius: 14px; padding: .8rem 1rem; height: auto; min-height: 3.4rem; white-space: normal; background: #FFFFFF; border: 1px solid #E3DFD2; }
[data-testid="stMainBlockContainer"] [data-testid="stButton"] button p { white-space: normal; text-align: left; width: 100%; }
[data-testid="stMainBlockContainer"] [data-testid="stButton"] button > div { width: 100%; justify-content: flex-start; }
[data-testid="stMainBlockContainer"] [data-testid="stButton"] button:hover { border-color: #2F6F62; color: #2F6F62; }

/* sign in */
.signin-title { font-family: 'Source Serif 4', Georgia, serif; font-size: 2rem; font-weight: 500; margin: 1.2rem 0 .2rem; }
.signin-sub { color: #6B675B; margin-bottom: 1.4rem; }
[data-testid="stForm"] { border: 1px solid #E3DFD2; border-radius: 16px; background: #FFFFFF; padding: 1.4rem; }
</style>
"""

for key, default in {"token": None, "user": None, "role": None, "api": DEFAULT_API,
                     "chats": {}, "chat_id": None, "pending": None, "view": None}.items():
    st.session_state.setdefault(key, default)
S = st.session_state

st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def claims(token):
    """Read the role from the JWT payload (display only; the server verifies it)."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def call(method, path, **kwargs):
    headers = {"Authorization": f"Bearer {S.token}"} if S.token else {}
    try:
        return requests.request(method, f"{S.api}{path}", headers=headers, timeout=300, **kwargs), None
    except requests.exceptions.ConnectionError:
        return None, f"Cannot reach the API at {S.api}. Is uvicorn running?"
    except requests.exceptions.Timeout:
        return None, "The request timed out."


def logout():
    for key in ("token", "user", "role", "chat_id", "pending", "view"):
        S[key] = None
    S.chats = {}


def new_chat():
    S.chat_id = None
    S.view = "chat"


def open_chat(chat_id):
    S.chat_id = chat_id
    S.view = "chat"


def go(view):
    S.view = view


def ask_suggestion(text):
    S.pending = text
    S.view = "chat"


def pretty_section(section):
    return section.replace("_", " ").capitalize()


def cite_html(text):
    """Escape model output, then turn [1] markers into small superscripts."""
    safe = html.escape(text).replace("$", "&#36;")
    return re.sub(r"\[(\d+)\]", r'<sup class="cite">\1</sup>', safe)


def reveal(text, placeholder):
    """Word-by-word display of an answer that is already complete."""
    words = text.split(" ")
    for i in range(1, len(words) + 1):
        placeholder.markdown(cite_html(" ".join(words[:i])), unsafe_allow_html=True)
        time.sleep(0.018)


# ---------------------------------------------------------------- rendering
def render_answer(res, animate=False):
    if res["abstained"]:
        why = REASONS.get(res["reason"], "There was not enough evidence to answer safely.")
        st.markdown('<span class="chip no">Declined</span>', unsafe_allow_html=True)
        st.markdown(f'<div class="decline"><b>I can\'t answer that from the labels.</b>{html.escape(why)}'
                    "<br>Try naming a drug and asking about its dosage, warnings, interactions, "
                    "side effects, uses or overdose.</div>", unsafe_allow_html=True)
    else:
        st.markdown('<span class="chip ok">Answered from label text</span>', unsafe_allow_html=True)
        box = st.empty()
        if animate:
            reveal(res["answer"], box)
        else:
            box.markdown(cite_html(res["answer"]), unsafe_allow_html=True)
        if res["citations"]:
            st.markdown('<div class="src-label">Sources</div>', unsafe_allow_html=True)
            for c in res["citations"]:
                with st.expander(f"{c['n']}   {c['drug'].title()}  |  {pretty_section(c['section'])}"):
                    st.markdown(f'<div class="excerpt">{html.escape(c.get("snippet") or "(no excerpt returned)")}</div>',
                                unsafe_allow_html=True)
                    st.caption(f"{c['manufacturer']}  |  chunk {c['chunk_id']}")
    st.markdown(f'<div class="meta">{res["seconds"]} s | request {res["request_id"][:8]} | '
                "Not medical advice. Verify against the full official label.</div>", unsafe_allow_html=True)


def render_message(msg, animate=False):
    if msg["role"] == "user":
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(html.escape(msg["content"]).replace("$", "&#36;"), unsafe_allow_html=True)
    else:
        with st.chat_message("assistant", avatar=":material/medication:"):
            if msg.get("error"):
                st.error(msg["error"])
            else:
                render_answer(msg["res"], animate)


def current_messages():
    return S.chats.get(S.chat_id, {}).get("messages", [])


def answer_question(question):
    """Send one question to the API. Returns an assistant message dict."""
    resp, err = call("POST", "/ask", json={"question": question})
    if err:
        return {"role": "assistant", "error": err}
    if resp.status_code == 200:
        return {"role": "assistant", "res": resp.json()}
    if resp.status_code == 401:
        logout()
        st.rerun()
    errors = {403: "Your role is not allowed to ask questions.",
              422: "Please type a question between 3 and 500 characters.",
              503: "The language model service is unavailable. Is Ollama running?"}
    return {"role": "assistant", "error": errors.get(resp.status_code, f"Unexpected error ({resp.status_code}).")}


# ---------------------------------------------------------------- views
def welcome():
    st.markdown(f'<div class="hero">Hello, {html.escape(S.user)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Ask about FDA prescription drug labels. Every answer cites its '
                "source text, or I will tell you that I can't answer.</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    for i, (tag, text) in enumerate(SUGGESTIONS):
        with cols[i % 2]:
            st.markdown(f'<div class="tag">{tag}</div>', unsafe_allow_html=True)
            st.button(text, key=f"sg{i}", on_click=ask_suggestion, args=(text,))


def chat_view():
    question = S.pending
    S.pending = None
    messages = current_messages()
    if not messages and not question:
        welcome()
    for msg in messages:
        render_message(msg)

    typed = st.chat_input("Ask about a prescription drug label...", max_chars=500)
    question = question or typed
    if not question:
        return

    if S.chat_id is None:
        S.chat_id = uuid.uuid4().hex[:8]
        S.chats[S.chat_id] = {"title": question[:42] + ("..." if len(question) > 42 else ""), "messages": []}
    user_msg = {"role": "user", "content": question}
    render_message(user_msg)
    with st.chat_message("assistant", avatar=":material/medication:"):
        with st.spinner("Searching the labels and writing a cited answer. This can take 20 to 40 seconds..."):
            reply = answer_question(question)
        if reply.get("error"):
            st.error(reply["error"])
        else:
            render_answer(reply["res"], animate=True)
    S.chats[S.chat_id]["messages"] += [user_msg, reply]
    st.rerun()   # redraw so the sidebar chat list is up to date


def audit_view():
    st.markdown('<div class="hero" style="margin-top:.5rem;font-size:2rem">Audit log</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Every login and question, recorded in a tamper-evident chain.</div>',
                unsafe_allow_html=True)
    resp, err = call("GET", "/audit", params={"limit": 50})
    if err:
        st.error(err)
        return
    if resp.status_code == 401:
        logout()
        st.rerun()
    if resp.status_code != 200:
        st.error("Your role cannot read the audit log." if resp.status_code == 403
                 else f"Unexpected error ({resp.status_code}).")
        return
    data = resp.json()
    if data["chain_intact"]:
        st.markdown('<span class="chip ok">Chain intact</span>', unsafe_allow_html=True)
    else:
        st.error("Audit chain BROKEN: the log has been edited or damaged.")
    records = [e["record"] for e in data["recent"]]
    asks = [r for r in records if r.get("event") == "ask"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Entries in log", data["total_entries"])
    c2.metric("Questions (recent)", len(asks))
    c3.metric("Declined (recent)", sum(1 for r in asks if r.get("abstained")))
    rows = [{"time": r.get("ts", ""), "event": r.get("event", ""), "user": r.get("user", ""),
             "decision": r.get("decision", ""), "question": r.get("question", "")}
            for r in reversed(records)]
    st.dataframe(rows, hide_index=True)


def login_view():
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'] {display:none}</style>",
                unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 4, 1])
    with mid:
        st.markdown('<div class="brand" style="margin-top:2rem"><span class="mark">M</span> MedLabel Assist</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="signin-title">Sign in</div>'
                    '<div class="signin-sub">Cited answers from FDA drug labels, or a clear refusal.</div>',
                    unsafe_allow_html=True)
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            resp, err = call("POST", "/login", json={"username": username, "password": password})
            if err:
                st.error(err)
            elif resp.status_code == 200:
                token = resp.json()["access_token"]
                S.token, S.user, S.role = token, claims(token)["sub"], claims(token)["role"]
                S.view = "audit" if S.role == "auditor" else "chat"
                st.rerun()
            else:
                st.error("Wrong username or password.")
        with st.expander("Demo accounts (local use only)"):
            st.markdown("- `analyst1` / `analyst-pass`: can ask questions\n"
                        "- `auditor1` / `auditor-pass`: can read the audit log\n"
                        "- `admin1` / `admin-pass`: both")
        with st.expander("Connection"):
            S.api = st.text_input("API address", S.api)


def sidebar():
    can_chat = S.role in ("analyst", "admin")
    can_audit = S.role in ("auditor", "admin")
    with st.sidebar:
        st.markdown('<div class="brand"><span class="mark">M</span> MedLabel Assist</div>', unsafe_allow_html=True)
        if can_chat:
            st.button("New chat", icon=":material/add:", on_click=new_chat, type="secondary", key="newchat")
        if can_chat and can_audit:
            st.markdown('<div class="side-label">Workspace</div>', unsafe_allow_html=True)
            st.button("Chat", icon=":material/chat:", on_click=go, args=("chat",), type="tertiary", key="nav_chat")
            st.button("Audit log", icon=":material/fact_check:", on_click=go, args=("audit",),
                      type="tertiary", key="nav_audit")
        if can_chat and S.chats:
            st.markdown('<div class="side-label">Recent</div>', unsafe_allow_html=True)
            for cid, chat in reversed(list(S.chats.items())):
                active = cid == S.chat_id and S.view == "chat"
                st.button(chat["title"], key=f"chat_{cid}", on_click=open_chat, args=(cid,),
                          type="secondary" if active else "tertiary")
        st.markdown('<div class="side-label">Account</div>', unsafe_allow_html=True)
        st.write(f"**{S.user}**  \n{S.role}")
        st.button("Sign out", icon=":material/logout:", on_click=logout, type="tertiary", key="signout")
        with st.expander("Connection"):
            S.api = st.text_input("API address", S.api)
            if st.button("Check connection"):
                resp, err = call("GET", "/health")
                if err:
                    st.error(err)
                else:
                    st.success("API is up") if resp.status_code == 200 else st.error("API error")


# ---------------------------------------------------------------- main
if not S.token:
    login_view()
    st.stop()

sidebar()
if S.view == "audit" and S.role in ("auditor", "admin"):
    audit_view()
else:
    chat_view()