"""Harbourlight Policy Assistant: the employee-facing app.

    streamlit run app/streamlit_app.py

Answers come only from approved, current policies the chosen role may see (D4, D5, D7, D8).
"""
from __future__ import annotations

import html
import os
import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so "app.pipeline" imports when run by Streamlit

# On Streamlit Cloud, keys come from the app's Secrets rather than a .env file.
try:
    for _k in ("LLM_PROVIDER", "LLM_MODEL", "ANTHROPIC_API_KEY"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:  # no secrets file locally
    pass

from app.pipeline import answer, documents, llm, store  # noqa: E402

st.set_page_config(page_title="Policy Assistant · Harbourlight", page_icon="📘", layout="wide")

# Off unless .env says otherwise. Streamlit Cloud has no .env, so the public site is read-only.
UPLOADS_ALLOWED = os.getenv("ALLOW_UPLOADS", "false").lower() == "true"
ROLE_INFO = {
    "Employee": "General policies, handbook and procedures.",
    "HR": "Everything an employee sees, plus HR-only procedures.",
    "Compliance": "Everything an employee sees, plus Compliance-only procedures.",
}
ACCESS_LABEL = {"all_staff": "All staff", "hr": "HR only", "compliance": "Compliance only"}
EXAMPLES = [
    "How much annual leave can I carry forward?",
    "What happens if I'm ill while on holiday?",
    "Can I play the slots at our casino on my day off?",
    "How do I report clicking a suspicious link?",
    "How many days a week can I work from home?",
]

# --- Styling ---------------------------------------------------------------------------------------
st.markdown("""
<style>
  #MainMenu, footer, [data-testid="stDecoration"] {display: none;}
  .block-container {padding-top: 1.2rem; max-width: 1180px;}
  .hl-header {background: linear-gradient(120deg, #0F2A44 0%, #173A5E 70%, #1E4A73 100%); color: #fff;
              border-radius: 14px; padding: 22px 28px; display: flex; align-items: center; gap: 18px;
              margin-bottom: 18px; box-shadow: 0 6px 20px rgba(15,42,68,.18);}
  .hl-logo {width: 48px; height: 48px; border-radius: 12px; background: #C8A24A; display: flex;
            align-items: center; justify-content: center; font-weight: 800; font-size: 24px; color: #0F2A44;}
  .hl-brand {font-size: 13px; letter-spacing: .14em; text-transform: uppercase; color: #C8D6E5;}
  .hl-title {font-size: 26px; font-weight: 700; line-height: 1.15;}
  .hl-sub {font-size: 14px; color: #C8D6E5; margin-top: 2px;}
  .hl-chip {margin-left: auto; background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.25);
            padding: 6px 12px; border-radius: 999px; font-size: 13px; white-space: nowrap;}
  .hl-card {background: #fff; border: 1px solid #E3E8EF; border-radius: 12px; padding: 18px 20px; margin-bottom: 12px;}
  .hl-status {display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px;
              padding: 5px 12px; border-radius: 999px; margin-bottom: 10px;}
  .hl-found {background: #E7F5EE; color: #146C43;}
  .hl-missing {background: #FFF4E0; color: #8A5300;}
  .hl-answer {font-size: 17px; line-height: 1.6; color: #1B2430;}
  .hl-meta {color: #5B6B7F; font-size: 13px; margin-top: 10px;}
  .hl-badge {display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 9px; border-radius: 999px;
             margin-right: 6px; border: 1px solid #D5DEE8; color: #33475B; background: #F4F6F9;}
  .hl-badge.gold {background: #FBF4E2; border-color: #E8D6A4; color: #7A5B12;}
  .hl-badge.red {background: #FDECEC; border-color: #F3C2C2; color: #A12828;}
  .hl-badge.green {background: #E7F5EE; border-color: #BFE3CF; color: #146C43;}
  .hl-table-wrap {background: #fff; border: 1px solid #E3E8EF; border-radius: 12px; overflow-x: auto; margin: 8px 0;}
  .hl-table {width: 100%; border-collapse: collapse; font-size: 14px;}
  .hl-table th {text-align: left; background: #F4F6F9; color: #5B6B7F; font-weight: 600; font-size: 12px;
                text-transform: uppercase; letter-spacing: .05em; padding: 10px 14px; border-bottom: 1px solid #E3E8EF;}
  .hl-table td {padding: 10px 14px; border-bottom: 1px solid #EEF1F5; vertical-align: top; color: #1B2430;}
  .hl-table tr:last-child td {border-bottom: none;}
  .hl-table tr.hl-old td {color: #8A97A8;}
  .hl-owner {color: #7A8899; font-size: 12px; margin-top: 2px;}
  .hl-source-title {font-weight: 600; color: #0F2A44; font-size: 15px;}
  .hl-section {color: #5B6B7F; font-size: 13px; margin: 2px 0 8px;}
  [class*="st-key-source-"] {border-left: 4px solid #C8A24A !important; background: #FFFDF7;}
  .hl-help {color: #5B6B7F; font-size: 14px; line-height: 1.55;}
  .stTabs [data-baseweb="tab-list"] {gap: 6px;}
  .stTabs [data-baseweb="tab"] {padding: 8px 14px; font-weight: 600;}
  section[data-testid="stSidebar"] {background: #0F2A44;}
  section[data-testid="stSidebar"] * {color: #E8EEF5 !important;}
  section[data-testid="stSidebar"] .hl-side-note {color: #A9BCD0 !important; font-size: 12.5px; line-height: 1.5;}
  section[data-testid="stSidebar"] button {background: rgba(255,255,255,.06) !important;
         border: 1px solid rgba(255,255,255,.15) !important;}
  /* Role switch: full-width options, the selected one in gold, no radio circles */
  section[data-testid="stSidebar"] [role="radiogroup"] {gap: 6px; width: 100%; align-items: stretch;}
  section[data-testid="stSidebar"] [data-testid="stRadio"], section[data-testid="stSidebar"] [data-testid="stRadio"] > div,
  section[data-testid="stSidebar"] [role="radiogroup"] > div {width: 100%;}
  section[data-testid="stSidebar"] [data-testid="stRadioOption"] {width: 100%; padding: 9px 12px; border-radius: 8px;
         border: 1px solid rgba(255,255,255,.18); cursor: pointer;}
  section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {display: none;}
  section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {background: #C8A24A; border-color: #C8A24A;}
  section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {color: #0F2A44 !important; font-weight: 700;}
  /* Question buttons: wrap long questions instead of cutting them off */
  [class*="st-key-example-"] button, [class*="st-key-recent-"] button {justify-content: flex-start; text-align: left;
         height: auto; padding: 8px 12px;}
  [class*="st-key-example-"] button p, [class*="st-key-recent-"] button p {white-space: normal !important;
         overflow: visible !important; text-overflow: clip !important; text-align: left; font-size: 14px;}
</style>
""", unsafe_allow_html=True)


# --- Data ------------------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Preparing the policy library…")
def load_library():
    docs = documents.load_all()
    store.ensure_index(docs, "section")  # rebuilds only if the documents changed
    return docs


def visible(docs, role):
    allowed = set(store.roles()[role])
    return [d for d in docs if d.meta["access_level"] in allowed]


docs = load_library()
today = date.today()

# --- Sidebar ---------------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Harbourlight")
    st.markdown('<div class="hl-side-note">Employee Policy Assistant</div>', unsafe_allow_html=True)
    st.divider()
    role = st.radio("View as", list(ROLE_INFO), key="role",
                    help="A demo switch. In production, your role would come from your company sign-in.")
    st.markdown(f'<div class="hl-side-note">{ROLE_INFO[role]}</div>', unsafe_allow_html=True)
    st.divider()
    history = st.session_state.setdefault("history", [])
    if history:
        st.markdown("**Recent questions**")
        for i, q in enumerate(reversed(history[-5:])):
            if st.button(q, key=f"recent-{i}", use_container_width=True):
                st.session_state["question"] = q
                st.session_state["run"] = True
        st.divider()
    st.markdown('<div class="hl-side-note">Answers come only from current, approved policies. '
                'Old versions are never used. Only your question and the matching policy passages are '
                'sent to the AI.<br><br>Harbourlight is a fictional company. All policies are mock '
                'documents for a portfolio project.</div>', unsafe_allow_html=True)

# --- Header ----------------------------------------------------------------------------------------
st.markdown(f"""
<div class="hl-header">
  <div class="hl-logo">H</div>
  <div>
    <div class="hl-brand">Harbourlight Casino Group · Internal</div>
    <div class="hl-title">Policy Assistant</div>
    <div class="hl-sub">Ask a question about company policy. Every answer shows the policy and section it came from.</div>
  </div>
  <div class="hl-chip">Viewing as <b>{html.escape(role)}</b></div>
</div>
""", unsafe_allow_html=True)

if llm.provider() == "mock":
    st.warning("**Demo mode:** no AI key is set, so answers are the first sentence of the best-matching "
               "passage, not AI. Add an API key to use Claude.", icon="⚠️")

ask_tab, library_tab, upload_tab, about_tab = st.tabs(["Ask a question", "Policy library", "Upload a policy", "How it works"])


# --- Ask -------------------------------------------------------------------------------------------
def show_answer(a: answer.Answer):
    if a.found:
        st.markdown(f"""<div class="hl-card"><span class="hl-status hl-found">✓ Answer found in approved policies</span>
            <div class="hl-answer">{html.escape(a.text)}</div>
            <div class="hl-meta">Answered in {a.seconds:.1f}s · Based on {len(a.sources)} policy
            passage{'s' if len(a.sources) != 1 else ''} · Viewing as {html.escape(role)}</div></div>""",
                    unsafe_allow_html=True)
        st.markdown("#### Sources")
        for i, h in enumerate(a.sources):
            with st.container(border=True, key=f"source-{i}"):
                where = f"§{h.section} {h.section_title}" if h.section else h.section_title
                st.markdown(f"""<div class="hl-source-title">{html.escape(h.title)}</div>
                    <div class="hl-section">{html.escape(where)}</div>
                    <span class="hl-badge gold">Version {html.escape(h.version)}</span>
                    <span class="hl-badge">Effective {h.effective_date:%-d %b %Y}</span>
                    <span class="hl-badge">{html.escape(h.department)}</span>""", unsafe_allow_html=True)
                st.markdown(h.text)
    else:
        st.markdown(f"""<div class="hl-card"><span class="hl-status hl-missing">ⓘ Not enough information</span>
            <div class="hl-answer">I don't have enough information in the approved policies to answer this.</div>
            <div class="hl-meta">Rather than guess, the assistant only answers when a current policy covers
            the question.<br>Please ask your line manager, or HR through the <b>HR Help</b> form on StaffHub.</div>
            </div>""", unsafe_allow_html=True)
    with st.expander(f"All passages searched ({len(a.retrieved)})"):
        st.caption("The closest passages from current policies you're allowed to see, best match first. "
                   "Match is how close in meaning each passage is to the question.")
        for h in a.retrieved:
            used = " · used in answer" if any(s.chunk_id == h.chunk_id for s in a.sources) else ""
            st.markdown(f"**{h.citation}**  \nMatch {h.score:.2f}{used}")


with ask_tab:
    left, right = st.columns([2.2, 1], gap="large")
    with right:
        st.markdown("#### Try asking")
        for i, q in enumerate(EXAMPLES):
            if st.button(q, key=f"example-{i}", use_container_width=True):
                st.session_state["question"] = q
                st.session_state["run"] = True
        st.markdown("""<div class="hl-card hl-help" style="margin-top:14px"><b>Good to know</b><br>
            • Answers come only from current policies.<br>
            • Each answer shows the exact policy text.<br>
            • If a policy doesn't cover it, you'll be told, not given a guess.<br>
            • For personal cases, always confirm with HR.</div>""", unsafe_allow_html=True)
    with left:
        with st.form("ask", border=False):
            question = st.text_input("Your question", key="question", placeholder="e.g. How much annual leave can I carry forward?",
                                     label_visibility="collapsed")
            submitted = st.form_submit_button("Ask", type="primary")
        run = submitted or st.session_state.pop("run", False)
        if run and question.strip():
            with st.spinner("Searching current policies…"):
                try:
                    result = answer.ask(question.strip(), role=role)
                    st.session_state["last"] = result
                    if question.strip() not in history:
                        history.append(question.strip())
                except llm.LLMError as exc:
                    st.error(str(exc))
        elif run:
            st.info("Type a question first.")
        if "last" in st.session_state:
            show_answer(st.session_state["last"])
        else:
            st.markdown("""<div class="hl-card hl-help">Ask about leave, sickness, working from home, conduct,
                security, expenses, training, incidents or complaints. You can use your own words.</div>""",
                        unsafe_allow_html=True)


# --- Library ---------------------------------------------------------------------------------------
with library_tab:
    mine = visible(docs, role)
    current = [d for d in mine if d.is_searchable(today)]
    overdue = [d for d in current if d.meta.get("review_date") and d.meta["review_date"] < today]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Searchable policies", len(current))
    c2.metric("Superseded (not searched)", sum(d.meta["status"] == "superseded" for d in mine))
    c3.metric("Restricted you can see", sum(d.meta["access_level"] != "all_staff" for d in mine))
    c4.metric("Overdue for review", len(overdue))

    dept = st.selectbox("Department", ["All departments"] + sorted({d.meta["department"] for d in mine}))
    rows = []
    for d in sorted(mine, key=lambda d: (d.meta["department"], d.meta["title"], str(d.meta["effective_date"]))):
        if dept != "All departments" and d.meta["department"] != dept:
            continue
        m, e = d.meta, html.escape
        if d.is_searchable(today):
            status = '<span class="hl-badge green">Current</span>'
        elif m["status"] == "superseded":
            status = '<span class="hl-badge">Superseded</span>'
        else:
            status = '<span class="hl-badge gold">Not yet in effect</span>'
        review = m.get("review_date")
        review_cell = f"{review:%-d %b %Y}" if review else "—"
        if review and review < today and d.is_searchable(today):
            review_cell += ' <span class="hl-badge red">Overdue</span>'
        access = ACCESS_LABEL[m["access_level"]]
        access_cell = access if m["access_level"] == "all_staff" else f'<span class="hl-badge gold">{access}</span>'
        rows.append(f'<tr class="{"" if d.is_searchable(today) else "hl-old"}"><td><b>{e(m["title"])}</b>'
                    f'<div class="hl-owner">{e(m["owner"])}</div></td><td>{e(m["department"])}</td>'
                    f'<td>{e(m["version"])}</td><td>{status}</td><td>{m["effective_date"]:%-d %b %Y}</td>'
                    f'<td>{access_cell}</td><td>{review_cell}</td></tr>')
    st.markdown('<div class="hl-table-wrap"><table class="hl-table"><thead><tr><th>Policy</th><th>Department</th>'
                '<th>Version</th><th>Status</th><th>Effective</th><th>Who can see it</th><th>Next review</th></tr>'
                f'</thead><tbody>{"".join(rows)}</tbody></table></div>', unsafe_allow_html=True)
    st.caption("Superseded policies stay listed for reference but are never used to answer questions.")

    labels = {f"{d.meta['title']} (v{d.meta['version']})": d for d in mine}
    pick = st.selectbox("Read a policy", ["Choose a policy…"] + list(labels))
    if pick in labels:
        d = labels[pick]
        if not d.is_searchable(today):
            st.warning("This version is superseded and is not used to answer questions.", icon="🗄️")
        with st.container(border=True):
            st.markdown(f"### {d.meta['title']}")
            st.caption(f"Version {d.meta['version']} · Effective {d.meta['effective_date']:%-d %b %Y} · "
                       f"{d.meta['department']} · {ACCESS_LABEL[d.meta['access_level']]} · Owner: {d.meta['owner']}")
            for s in d.sections:
                st.markdown(f"**{('§' + s.number + ' ') if s.number else ''}{s.title}**")
                st.markdown(s.text)


# --- Upload ----------------------------------------------------------------------------------------
with upload_tab:
    st.markdown("#### Add a policy document")
    if UPLOADS_ALLOWED:
        st.caption("PDF, Word (.docx), Markdown or text. Every document needs its details filled in before it "
                   "can be searched. In production, only policy owners would be able to upload.")
        file = st.file_uploader("Policy file", type=["pdf", "docx", "md", "txt"])
    else:
        file = None
        st.info("Uploads are switched off on this public demo, so nobody can change the policies other "
                "visitors see. To try uploading, run the app on your own computer (see the README).", icon="🔒")
    if file:
        data = file.getvalue()
        found = documents.read_header(data) if file.name.lower().endswith((".md", ".txt")) else {}
        if found:
            st.info("Details found in the file have been filled in below. Check them before saving.")
        with st.form("upload"):
            a, b = st.columns(2)
            title = a.text_input("Policy title *", value=found.get("title", ""))
            dept_default = found.get("department", "HR")
            department = b.selectbox("Department *", documents.DEPARTMENTS,
                                     index=documents.DEPARTMENTS.index(dept_default) if dept_default in documents.DEPARTMENTS else 1)
            version = a.text_input("Version *", value=str(found.get("version", "1.0")))
            access_keys = list(ACCESS_LABEL)
            access = b.selectbox("Who can see it *", access_keys, format_func=ACCESS_LABEL.get,
                                 index=access_keys.index(found.get("access_level", "all_staff"))
                                 if found.get("access_level") in access_keys else 0)
            effective = a.date_input("Effective date *", value=found.get("effective_date") if isinstance(found.get("effective_date"), date) else today)
            review = b.date_input("Next review date", value=None)
            owner = a.text_input("Owner (job title) *", value=found.get("owner", ""))
            replaceable = {f"{d.meta['title']} (v{d.meta['version']})": d.doc_id for d in docs if d.meta["status"] == "current"}
            replaces = b.selectbox("Replaces an existing policy?", ["No, it's a new policy"] + list(replaceable),
                                   help="The policy it replaces will be marked superseded and no longer searched.")
            save = st.form_submit_button("Save and add to search", type="primary")
        if save:
            meta = {"title": title.strip(), "department": department, "version": version.strip(),
                    "access_level": access, "effective_date": effective, "owner": owner.strip(),
                    "review_date": review, "supersedes": replaceable.get(replaces)}
            try:
                doc = documents.save_upload(file.name, data, meta, docs)
            except documents.HeaderError as exc:
                st.error(str(exc).split(": ", 1)[-1])
            else:
                with st.spinner("Adding to search…"):
                    load_library.clear()
                    docs = load_library()
                msg = f"**{doc.meta['title']}** was added with {len(doc.sections)} section(s)."
                if meta["supersedes"]:
                    msg += f" **{replaces}** is now superseded and won't be used in answers."
                if effective > today:
                    msg += f" It will be used from {effective:%-d %b %Y}."
                st.success(msg)


# --- How it works ----------------------------------------------------------------------------------
with about_tab:
    st.markdown("#### How the assistant answers")
    st.markdown("""
1. **Filter.** Only policies that are **current**, **already in effect** and that **your role may see** are searched.
   Old versions and restricted documents are removed before searching, so they can never appear in an answer.
2. **Search.** Your question is matched by meaning (not just keywords) against each policy section.
3. **Check.** If nothing is close enough, you're told there isn't enough information, and the AI isn't asked at all.
4. **Answer.** Claude writes a short answer using only those sections and must say which ones it used.
5. **Verify.** The app checks those sections were really found, and shows you the exact policy text.
""")
    st.markdown("#### What this assistant won't do")
    st.markdown("- Use an old version of a policy\n- Answer from general knowledge or guess a rule\n"
                "- Show documents your role can't access\n- Replace advice from HR on personal cases")
    st.caption(f"AI model: {llm.model_name()} · Prompt: {answer.PROMPT_VERSION} · "
               f"{len([d for d in docs if d.is_searchable(today)])} searchable policies")
