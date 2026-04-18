"""
ResearchPilot — Streamlit Frontend
Real-time agentic research assistant UI.
"""

import time
import httpx
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResearchPilot",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Backend URL ───────────────────────────────────────────────────────────────
import os
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background: #0f0f13; }
  .main-title {
    font-size: 2.4rem; font-weight: 700; color: #fff;
    text-align: center; margin-bottom: 0.2rem;
  }
  .sub-title {
    font-size: 1rem; color: #888; text-align: center; margin-bottom: 2rem;
  }
  .event-card {
    padding: 8px 14px; border-radius: 8px; margin: 4px 0;
    font-family: monospace; font-size: 0.85rem;
  }
  .ev-status   { background: #1e3a5f; color: #7ecfff; }
  .ev-thinking { background: #2a1f4e; color: #b69fff; }
  .ev-plan     { background: #1a3a2a; color: #6fe09f; }
  .ev-question { background: #3a2a10; color: #ffcc70; }
  .ev-tool_call{ background: #1f1f1f; color: #aaa; }
  .ev-tool_result{ background: #1a2a1a; color: #7fb87f; }
  .ev-finding  { background: #2a1a2a; color: #e09fff; }
  .ev-gap      { background: #3a1a10; color: #ff9070; }
  .ev-log      { background: #1a1a1a; color: #666; }
  .report-box  {
    background: #13131b; border: 1px solid #333; border-radius: 12px;
    padding: 2rem; margin-top: 1rem;
  }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🔬 ResearchPilot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Agentic AI Research Assistant — Plan → Search → Synthesize → Report</div>', unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    max_iterations = st.slider("Max research iterations", 1, 5, 2)
    output_format = st.radio("Output format", ["markdown", "pdf"], index=0)
    st.divider()
    st.markdown("**How it works:**")
    st.markdown("""
1. 🧠 **Plan** — breaks topic into sub-questions  
2. 🔍 **Search** — finds relevant web sources  
3. 📄 **Scrape** — reads page content  
4. ✍️ **Synthesize** — LLM summarizes findings  
5. 🔎 **Gap check** — identifies missing info  
6. 🔁 **Repeat** if needed  
7. 📋 **Report** — final structured output  
""")
    st.divider()
    st.caption("Built with FastAPI · Claude API · Docker · AWS ECS")

# ── Main input ────────────────────────────────────────────────────────────────
col1, col2 = st.columns([5, 1])
with col1:
    topic = st.text_input(
        "Research topic",
        placeholder="e.g. Latest advances in quantum computing",
        label_visibility="collapsed",
    )
with col2:
    start = st.button("🚀 Research", use_container_width=True, type="primary")

# ── State ─────────────────────────────────────────────────────────────────────
if "events" not in st.session_state:
    st.session_state.events = []
if "report" not in st.session_state:
    st.session_state.report = ""
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "running" not in st.session_state:
    st.session_state.running = False

# ── Research execution ────────────────────────────────────────────────────────
if start and topic:
    st.session_state.events = []
    st.session_state.report = ""
    st.session_state.running = True

    # Start session
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/research/start",
            json={"topic": topic, "max_iterations": max_iterations, "output_format": output_format},
            timeout=10,
        )
        resp.raise_for_status()
        session_id = resp.json()["session_id"]
        st.session_state.session_id = session_id
    except Exception as e:
        st.error(f"Failed to connect to backend: {e}")
        st.session_state.running = False
        st.stop()

    # Stream events
    st.subheader("🤖 Agent Activity")
    log_container = st.container()
    report_placeholder = st.empty()
    progress = st.progress(0, text="Starting research...")

    event_log = []
    final_report = ""
    step = 0
    total_steps = max_iterations * 8  # rough estimate

    try:
        with httpx.stream(
            "GET",
            f"{BACKEND_URL}/research/stream/{session_id}",
            params={"topic": topic, "max_iterations": max_iterations},
            timeout=300,
        ) as stream_resp:
            for line in stream_resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if "||" not in payload:
                    continue
                event_type, content = payload.split("||", 1)

                step += 1
                progress.progress(min(step / total_steps, 0.95), text=f"Step {step}: {event_type}")

                if event_type == "final_report":
                    final_report = content
                    st.session_state.report = content
                elif event_type == "done":
                    break
                elif event_type == "error":
                    st.error(f"Agent error: {content}")
                    break
                else:
                    event_log.append((event_type, content))
                    st.session_state.events = list(event_log)

                    # Render event log
                    with log_container:
                        for ev_type, ev_content in event_log[-20:]:  # show last 20 events
                            css_class = f"ev-{ev_type}" if ev_type in [
                                "status","thinking","plan","question","tool_call",
                                "tool_result","finding","gap","log"
                            ] else "ev-log"
                            icon = {
                                "status": "●", "thinking": "◌", "plan": "▸",
                                "question": "?", "tool_call": "⚡", "tool_result": "✓",
                                "finding": "★", "gap": "!", "log": "·"
                            }.get(ev_type, "·")
                            display = ev_content[:120] + ("..." if len(ev_content) > 120 else "")
                            st.markdown(
                                f'<div class="event-card {css_class}">{icon} <b>{ev_type}</b>: {display}</div>',
                                unsafe_allow_html=True,
                            )

        progress.progress(1.0, text="✅ Research complete!")

    except Exception as e:
        st.error(f"Streaming error: {e}")

    st.session_state.running = False

# ── Report display ────────────────────────────────────────────────────────────
if st.session_state.report:
    st.divider()
    st.subheader("📋 Research Report")

    tab1, tab2 = st.tabs(["📖 Rendered", "📝 Raw Markdown"])
    with tab1:
        st.markdown(st.session_state.report)
    with tab2:
        st.code(st.session_state.report, language="markdown")

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "⬇️ Download Markdown",
            data=st.session_state.report,
            file_name="research_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_b:
        if st.session_state.session_id:
            if st.button("⬇️ Download PDF", use_container_width=True):
                try:
                    pdf_resp = httpx.get(
                        f"{BACKEND_URL}/research/result/{st.session_state.session_id}",
                        params={"format": "pdf"},
                        timeout=60,
                    )
                    if pdf_resp.status_code == 200:
                        st.download_button(
                            "Click to save PDF",
                            data=pdf_resp.content,
                            file_name="research_report.pdf",
                            mime="application/pdf",
                        )
                    else:
                        st.error("PDF generation failed.")
                except Exception as e:
                    st.error(f"PDF error: {e}")

elif not st.session_state.running and st.session_state.events:
    # Show past events if research ran but no report
    st.subheader("🤖 Agent Activity")
    for ev_type, ev_content in st.session_state.events:
        st.markdown(f"**{ev_type}**: {ev_content[:200]}")

# ── Empty state ───────────────────────────────────────────────────────────────
if not topic and not st.session_state.report:
    st.info("👆 Enter a research topic above and click **Research** to begin.")
    st.markdown("**Example topics:**")
    examples = [
        "Latest advances in quantum computing",
        "Impact of generative AI on software development",
        "CRISPR gene editing applications in medicine",
        "Renewable energy storage technologies 2024",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        with cols[i % 2]:
            st.markdown(f"- {ex}")
