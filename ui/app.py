"""
ui/app.py
Streamlit frontend for BankGuard AI — 3 pages:
  1. Case Submission
  2. Live Investigation Dashboard
  3. Case History
"""

import io
import json
import os
import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="BankGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main { background: #0a0e1a; }

.metric-card {
    background: linear-gradient(135deg, #1a1f35 0%, #0f1628 100%);
    border: 1px solid #2a3050;
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.5rem 0;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}
.risk-clear  { border-left: 4px solid #00c896; }
.risk-low    { border-left: 4px solid #f0c040; }
.risk-medium { border-left: 4px solid #ff8c42; }
.risk-high   { border-left: 4px solid #ff4d6d; }

.agent-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 2px;
}
.badge-running  { background: #1e3a5f; color: #60b4ff; }
.badge-done     { background: #0d3326; color: #00c896; }
.badge-flagged  { background: #3d1a22; color: #ff4d6d; }

.score-label {
    font-size: 2.5rem;
    font-weight: 700;
    text-align: center;
}
.flag-item {
    background: #1a0d1a;
    border-left: 3px solid #ff4d6d;
    padding: 6px 12px;
    border-radius: 4px;
    margin: 4px 0;
    font-size: 0.87rem;
    color: #ffb3c1;
}
.report-box {
    background: #0f1628;
    border: 1px solid #2a3050;
    border-radius: 8px;
    padding: 1.2rem;
    font-family: monospace;
    font-size: 0.85rem;
    white-space: pre-wrap;
    color: #c8d6f0;
    max-height: 500px;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)


# ── Sidebar navigation ─────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/security-shield-green.png", width=60)
    st.markdown("## 🛡️ BankGuard AI")
    st.markdown("*Intelligent Fraud Detection*")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📋 Case Submission", "🔍 Investigation Dashboard", "📂 Case History"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(f"**API:** `{API_BASE}`")
    if st.button("🔄 Health Check"):
        try:
            r = requests.get(f"{API_BASE}/api/health", timeout=5)
            st.success(f"✅ API Online — v{r.json().get('version','?')}")
        except Exception:
            st.error("❌ API Offline")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 1 — Case Submission
# ═══════════════════════════════════════════════════════════════════════════
if page == "📋 Case Submission":
    st.title("📋 New Fraud Investigation Case")
    st.markdown("Upload KYC documents, transaction history, and loan application details.")

    with st.form("case_form", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📄 KYC Documents")
            aadhaar_file = st.file_uploader("Aadhaar Card", type=["jpg", "jpeg", "png", "pdf"], key="aadhaar")
            pan_file = st.file_uploader("PAN Card", type=["jpg", "jpeg", "png", "pdf"], key="pan")
            salary_file = st.file_uploader("Salary Slip", type=["jpg", "jpeg", "png", "pdf"], key="salary")
            bank_stmt_file = st.file_uploader("Bank Statement", type=["jpg", "jpeg", "png", "pdf"], key="bank")
            tx_file = st.file_uploader("Transaction History (CSV)", type=["csv"], key="txcsv")

        with col2:
            st.subheader("🏦 Loan Application")
            applicant_name = st.text_input("Full Name *", placeholder="Rajesh Kumar Singh")
            dob = st.text_input("Date of Birth *", placeholder="15/08/1985")
            employer = st.text_input("Employer *", placeholder="Infosys Limited")
            income = st.number_input("Monthly Income (₹) *", min_value=0.0, step=1000.0, value=75000.0)
            loan_amount = st.number_input("Loan Amount Requested (₹) *", min_value=0.0, step=10000.0, value=500000.0)
            loan_purpose = st.selectbox("Loan Purpose", ["Home Loan", "Personal Loan", "Business Loan", "Vehicle Loan", "Education Loan"])
            address = st.text_area("Address", placeholder="123 MG Road, Bangalore - 560001")
            phone = st.text_input("Phone", placeholder="+91 98765 43210")
            email = st.text_input("Email", placeholder="rajesh@email.com")

        submitted = st.form_submit_button("🚀 Run Fraud Analysis", use_container_width=True, type="primary")

    if submitted:
        if not applicant_name or not dob or not employer:
            st.error("Please fill in all required fields (Name, DOB, Employer).")
            st.stop()

        # Step 1: Upload documents
        with st.status("⬆️ Uploading documents…", expanded=True) as status:
            upload_files = {}
            if aadhaar_file:
                upload_files["aadhaar"] = (aadhaar_file.name, aadhaar_file.getvalue(), aadhaar_file.type)
            if pan_file:
                upload_files["pan"] = (pan_file.name, pan_file.getvalue(), pan_file.type)
            if salary_file:
                upload_files["salary_slip"] = (salary_file.name, salary_file.getvalue(), salary_file.type)
            if bank_stmt_file:
                upload_files["bank_statement"] = (bank_stmt_file.name, bank_stmt_file.getvalue(), bank_stmt_file.type)

            multipart = {k: (v[0], io.BytesIO(v[1]), v[2]) for k, v in upload_files.items()}
            if tx_file:
                multipart["transactions_csv"] = (tx_file.name, io.BytesIO(tx_file.getvalue()), "text/csv")

            try:
                upload_resp = requests.post(f"{API_BASE}/api/upload", files=multipart, timeout=30)
                upload_resp.raise_for_status()
                case_id = upload_resp.json()["case_id"]
                status.update(label=f"✅ Uploaded — Case ID: `{case_id}`", state="complete")
            except Exception as e:
                status.update(label="❌ Upload failed", state="error")
                st.error(f"Upload error: {e}")
                st.stop()

        # Step 2: Trigger analysis
        with st.status("🔬 Running multi-agent analysis…", expanded=True) as status:
            payload = {
                "case_id": case_id,
                "loan_form": {
                    "name": applicant_name,
                    "dob": dob,
                    "employer": employer,
                    "income": income,
                    "loan_amount": loan_amount,
                    "loan_purpose": loan_purpose,
                    "address": address,
                    "phone": phone,
                    "email": email,
                },
                "human_approved": False,
                "human_notes": "",
            }
            try:
                analyze_resp = requests.post(
                    f"{API_BASE}/api/analyze",
                    json=payload,
                    timeout=300,
                )
                analyze_resp.raise_for_status()
                report = analyze_resp.json()
                st.session_state["last_report"] = report
                status.update(label="✅ Analysis complete!", state="complete")
            except Exception as e:
                status.update(label="❌ Analysis failed", state="error")
                st.error(f"Analysis error: {e}")
                st.stop()

        st.success(f"✅ Case **{case_id}** analysed. Switch to **Investigation Dashboard** to view results.")
        st.balloons()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 2 — Investigation Dashboard
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🔍 Investigation Dashboard":
    st.title("🔍 Live Investigation Dashboard")

    report = st.session_state.get("last_report")

    if not report:
        case_id_input = st.text_input("Enter Case ID to load report:", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        if st.button("Load Case") and case_id_input:
            try:
                r = requests.get(f"{API_BASE}/api/cases/{case_id_input}", timeout=15)
                r.raise_for_status()
                report = r.json()
                st.session_state["last_report"] = report
                st.rerun()
            except Exception as e:
                st.error(f"Could not load case: {e}")
        st.info("💡 Submit a case on the **Case Submission** page first, or enter a Case ID above.")
        st.stop()

    # ── Header ─────────────────────────────────────────────────────────────
    fraud_score = report.get("fraud_score", 0)
    recommendation = report.get("recommendation", "Review")
    case_id = report.get("case_id", "N/A")

    rec_color = {"Approve": "#00c896", "Review": "#f0c040", "Reject & Escalate": "#ff4d6d"}.get(recommendation, "#aaa")
    rec_emoji = {"Approve": "✅", "Review": "⚠️", "Reject & Escalate": "🚨"}.get(recommendation, "❓")

    st.markdown(f"""
    <div class="metric-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="color:#8a9bc0; font-size:0.85rem;">CASE ID</div>
                <div style="font-size:1.1rem; font-weight:600; color:#e0e8ff;">{case_id}</div>
            </div>
            <div style="text-align:center;">
                <div style="color:#8a9bc0; font-size:0.85rem;">FRAUD SCORE</div>
                <div class="score-label" style="color:{rec_color};">{fraud_score:.1f}</div>
                <div style="color:#8a9bc0; font-size:0.75rem;">/ 100</div>
            </div>
            <div style="text-align:right;">
                <div style="color:#8a9bc0; font-size:0.85rem;">RECOMMENDATION</div>
                <div style="font-size:1.4rem; font-weight:700; color:{rec_color};">{rec_emoji} {recommendation}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Agent status tracker ────────────────────────────────────────────────
    st.subheader("🤖 Agent Pipeline Status")
    agents = [
        ("OCRAgent", "done", "📄"),
        ("KYCVerificationAgent", "done" if report.get("kyc_result") else "running", "🪪"),
        ("TransactionAnalystAgent", "done" if report.get("transaction_result") else "running", "💳"),
        ("LoanDocumentAgent", "done" if report.get("loan_result") else "running", "📋"),
        ("CrossReferenceAgent", "done" if report.get("cross_ref_result") else "running", "🔗"),
        ("RiskScoringAgent", "done", "📊"),
    ]
    cols = st.columns(len(agents))
    for col, (name, status_val, emoji) in zip(cols, agents):
        badge_class = f"badge-{status_val}"
        col.markdown(f"""
        <div style="text-align:center; padding:0.5rem;">
            <div style="font-size:1.5rem;">{emoji}</div>
            <div style="font-size:0.72rem; color:#8a9bc0;">{name}</div>
            <span class="agent-badge {badge_class}">{status_val.upper()}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Fraud Score Gauge + Score Breakdown ────────────────────────────────
    col_gauge, col_breakdown = st.columns([1, 1])

    with col_gauge:
        st.subheader("📊 Fraud Score Gauge")
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=fraud_score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Fraud Risk Score", "font": {"size": 16, "color": "#8a9bc0"}},
            number={"font": {"size": 40, "color": rec_color}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#8a9bc0"},
                "bar": {"color": rec_color},
                "bgcolor": "#1a1f35",
                "steps": [
                    {"range": [0, 35], "color": "#0d3326"},
                    {"range": [35, 70], "color": "#2d2810"},
                    {"range": [70, 100], "color": "#3d1a22"},
                ],
                "threshold": {
                    "line": {"color": "#ff4d6d", "width": 3},
                    "thickness": 0.85,
                    "value": 70,
                },
            },
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#c8d6f0"},
            height=280,
            margin=dict(t=40, b=10, l=20, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_breakdown:
        st.subheader("📈 Score Breakdown")
        sb = report.get("score_breakdown") or {}
        breakdown_data = {
            "KYC": sb.get("kyc_score", 0),
            "Transactions": sb.get("transaction_score", 0),
            "Loan Docs": sb.get("loan_score", 0),
            "Cross-Reference": sb.get("cross_ref_score", 0),
        }
        fig2 = go.Figure(go.Bar(
            x=list(breakdown_data.keys()),
            y=list(breakdown_data.values()),
            marker_color=["#60b4ff", "#f0c040", "#ff8c42", "#c77dff"],
            text=[f"{v:.1f}" for v in breakdown_data.values()],
            textposition="outside",
        ))
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#c8d6f0"},
            yaxis={"range": [0, 110], "gridcolor": "#2a3050"},
            xaxis={"gridcolor": "#2a3050"},
            height=280,
            margin=dict(t=20, b=10, l=20, r=20),
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Per-domain risk cards ───────────────────────────────────────────────
    st.subheader("🃏 Domain Risk Cards")
    d1, d2, d3 = st.columns(3)

    kyc = report.get("kyc_result", {})
    tx = report.get("transaction_result", {})
    loan = report.get("loan_result", {})
    xref = report.get("cross_ref_result", {})

    kyc_status = kyc.get("kyc_status", "unknown")
    kyc_class = {"clear": "risk-clear", "suspicious": "risk-medium", "failed": "risk-high"}.get(kyc_status, "risk-medium")
    d1.markdown(f"""
    <div class="metric-card {kyc_class}">
        <div style="color:#8a9bc0;font-size:0.8rem;">KYC / DOCUMENT</div>
        <div style="font-size:1.3rem;font-weight:700;color:#e0e8ff;text-transform:uppercase;">{kyc_status}</div>
        <div style="color:#8a9bc0;font-size:0.8rem;">Confidence: {kyc.get('confidence',0):.1f}%</div>
        <div style="color:#ff8c42;font-size:0.8rem;">{len(kyc.get('flags',[]))} flags</div>
    </div>
    """, unsafe_allow_html=True)

    tx_level = tx.get("risk_level", "clear")
    tx_class = {"clear": "risk-clear", "low": "risk-low", "medium": "risk-medium", "high": "risk-high"}.get(tx_level, "risk-medium")
    d2.markdown(f"""
    <div class="metric-card {tx_class}">
        <div style="color:#8a9bc0;font-size:0.8rem;">TRANSACTIONS</div>
        <div style="font-size:1.3rem;font-weight:700;color:#e0e8ff;text-transform:uppercase;">{tx_level}</div>
        <div style="color:#8a9bc0;font-size:0.8rem;">Anomaly Score: {tx.get('anomaly_score',0):.1f}</div>
        <div style="color:#ff8c42;font-size:0.8rem;">{tx.get('flagged_count',0)}/{tx.get('total_transactions',0)} flagged</div>
    </div>
    """, unsafe_allow_html=True)

    loan_ok = loan.get("income_match") and loan.get("employer_verified")
    loan_class = "risk-clear" if loan_ok else ("risk-high" if len(loan.get("flags",[])) >= 3 else "risk-medium")
    loan_status = "Verified" if loan_ok else "Issues Found"
    d3.markdown(f"""
    <div class="metric-card {loan_class}">
        <div style="color:#8a9bc0;font-size:0.8rem;">LOAN APPLICATION</div>
        <div style="font-size:1.3rem;font-weight:700;color:#e0e8ff;">{loan_status}</div>
        <div style="color:#8a9bc0;font-size:0.8rem;">Income Match: {'✅' if loan.get('income_match') else '❌'} | Employer: {'✅' if loan.get('employer_verified') else '❌'}</div>
        <div style="color:#ff8c42;font-size:0.8rem;">{len(loan.get('flags',[]))} flags</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Expandable detail sections ──────────────────────────────────────────
    st.markdown("---")
    with st.expander("🪪 KYC Findings", expanded=False):
        for flag in kyc.get("flags", []):
            st.markdown(f'<div class="flag-item">⚠️ {flag}</div>', unsafe_allow_html=True)
        if kyc.get("llm_analysis"):
            st.json(kyc["llm_analysis"])

    with st.expander("💳 Transaction Analysis", expanded=False):
        st.write(f"**LLM Summary:** {tx.get('llm_summary','N/A')}")
        if tx.get("flagged_transactions"):
            st.dataframe(pd.DataFrame(tx["flagged_transactions"]), use_container_width=True)
        if tx.get("structuring_flags"):
            st.warning(f"⚠️ Structuring detected: {len(tx['structuring_flags'])} transactions just below ₹1,00,000")
        if tx.get("velocity_flags"):
            st.error(f"🚨 Velocity/geo fraud: {len(tx['velocity_flags'])} multi-city transactions")

    with st.expander("📋 Loan Document Analysis", expanded=False):
        st.write(f"**Income:** {loan.get('income_message','N/A')}")
        st.write(f"**Employer:** {loan.get('employer_message','N/A')}")
        for flag in loan.get("flags", []):
            st.markdown(f'<div class="flag-item">⚠️ {flag}</div>', unsafe_allow_html=True)

    with st.expander("🔗 Cross-Reference Analysis", expanded=False):
        st.metric("Cross-Match Score", f"{xref.get('cross_match_score',0):.1f}/100")
        if xref.get("mismatches"):
            for m in xref["mismatches"]:
                st.markdown(f'<div class="flag-item">❌ {m}</div>', unsafe_allow_html=True)
        if xref.get("similar_cases"):
            st.write(f"**Similar past fraud cases found:** {len(xref['similar_cases'])}")
            st.json(xref["similar_cases"])

    # ── Final Report ────────────────────────────────────────────────────────
    st.subheader("📝 Investigator Report")
    final_report = report.get("final_report", "No report generated.")
    st.markdown(f'<div class="report-box">{final_report}</div>', unsafe_allow_html=True)

    # Download PDF
    if st.button("⬇️ Download Report as PDF"):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(f"BankGuard AI — Fraud Investigation Report", styles["Title"]),
                Paragraph(f"Case ID: {case_id}", styles["Normal"]),
                Paragraph(f"Fraud Score: {fraud_score:.1f}/100", styles["Normal"]),
                Paragraph(f"Recommendation: {recommendation}", styles["Normal"]),
                Spacer(1, 12),
                Paragraph("Investigator Report:", styles["Heading2"]),
                Paragraph(final_report.replace("\n", "<br/>"), styles["Normal"]),
            ]
            doc.build(story)
            st.download_button(
                "📥 Click to Download PDF",
                data=buf.getvalue(),
                file_name=f"bankguard_{case_id[:8]}.pdf",
                mime="application/pdf",
            )
        except ImportError:
            st.warning("Install `reportlab` to enable PDF export.")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 3 — Case History
# ═══════════════════════════════════════════════════════════════════════════
elif page == "📂 Case History":
    st.title("📂 Case History")

    col_filter1, col_filter2, col_refresh = st.columns([1, 1, 0.3])
    with col_filter1:
        rec_filter = st.selectbox("Filter by Recommendation", ["All", "Approve", "Review", "Reject & Escalate"])
    with col_filter2:
        limit = st.number_input("Results per page", min_value=5, max_value=100, value=20)
    with col_refresh:
        st.write("")
        refresh = st.button("🔄 Refresh")

    params = {"limit": limit}
    if rec_filter != "All":
        params["recommendation"] = rec_filter

    try:
        resp = requests.get(f"{API_BASE}/api/cases", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cases = data.get("cases", [])
        total = data.get("total", 0)
    except Exception as e:
        st.error(f"Could not load cases: {e}")
        cases = []
        total = 0

    st.markdown(f"**{total} case(s) found**")

    if not cases:
        st.info("No cases yet. Submit your first case on the Case Submission page.")
        st.stop()

    df = pd.DataFrame(cases)
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")

    def color_rec(val):
        colors = {"Approve": "color: #00c896", "Review": "color: #f0c040", "Reject & Escalate": "color: #ff4d6d"}
        return colors.get(val, "")

    st.dataframe(
        df[["case_id", "created_at", "fraud_score", "recommendation", "status"]].style.applymap(
            color_rec, subset=["recommendation"]
        ),
        use_container_width=True,
        height=400,
    )

    st.subheader("🔎 View Case Detail")
    selected_id = st.text_input("Paste Case ID:")
    if st.button("Load Full Report") and selected_id:
        try:
            r = requests.get(f"{API_BASE}/api/cases/{selected_id}", timeout=10)
            r.raise_for_status()
            st.session_state["last_report"] = r.json()
            st.success("Report loaded! Switch to Investigation Dashboard to view.")
        except Exception as e:
            st.error(f"Error: {e}")
