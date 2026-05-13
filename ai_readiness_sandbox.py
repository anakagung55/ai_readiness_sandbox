import streamlit as st
import google.generativeai as genai
import json
import os
import re
from dotenv import load_dotenv

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
st.set_page_config(page_title="BlueRock AI Readiness POC", layout="wide")

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1B263B; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stProgress > div > div > div > div { background-color: #4ade80; }
    .chat-container { padding: 20px; }
    </style>
    """, unsafe_allow_html=True)

load_dotenv()
# Pastikan menggunakan gemini-1.5-flash untuk stabilitas
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 2. THE MASTER SYSTEM PROMPT (WITH STOPPING CONDITION & FALLBACK)
# ==========================================
SYSTEM_PROMPT = """
You are the BlueRock AI Readiness Consultant, an expert conversational agent.
Your objective is to conduct a dynamic assessment to determine a company's AI Readiness across 6 pillars.

THE 6 PILLARS (Score 0-100):
1. Strategy & Vision
2. Data Maturity
3. Technical Infrastructure
4. Talent & Skills
5. Governance & Risk
6. Culture & Adoption

YOUR INSTRUCTIONS:
1. Start by asking Tier 1 context: Company industry, size, and current AI engagement (Exploring, Piloting, Production, or Core).
2. ADAPTIVE DEPTH: Branch your questions based on answers. Uncover pain points.
3. CONTRADICTION DETECTION: Politely challenge contradicting statements.
4. OUT OF SCOPE / PRICING: If the user asks about specific costs or pricing, politely explain that you are an assessment agent and a human consultant will discuss custom pricing later. DO NOT break the JSON format.
5. STOPPING CONDITION (CRITICAL): Monitor the 6 pillar scores. Once ALL 6 pillars have a score greater than 0, you MUST STOP asking questions. Your agent_reply MUST be exactly: "Thank you for sharing those insights. I have gathered enough information to complete your assessment. I am generating your personalized AI Readiness Roadmap now."

CRITICAL OUTPUT FORMAT:
You MUST respond STRICTLY in the following JSON format. No extra text, no markdown block quotes outside the JSON.
{
  "agent_reply": "Your conversational response here...",
  "current_scores": {
    "Strategy & Vision": 10,
    "Data Maturity": 20,
    "Technical Infrastructure": 15,
    "Talent & Skills": 5,
    "Governance & Risk": 0,
    "Culture & Adoption": 10
  }
}
"""

# ==========================================
# 3. STATE MANAGEMENT
# ==========================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "model", "parts": [SYSTEM_PROMPT]}
    ]
if "display_messages" not in st.session_state:
    st.session_state.display_messages = [
        {"role": "assistant", "content": "Hi there! I'm the BlueRock AI Readiness Agent. To get started, could you tell me a bit about your organisation—specifically your industry, approximate headcount, and where you currently stand with AI?"}
    ]
if "pillar_scores" not in st.session_state:
    st.session_state.pillar_scores = {
        "Strategy & Vision": 0, "Data Maturity": 0, "Technical Infrastructure": 0,
        "Talent & Skills": 0, "Governance & Risk": 0, "Culture & Adoption": 0
    }
if "assessment_complete" not in st.session_state:
    st.session_state.assessment_complete = False

# ==========================================
# 4. SIDEBAR: REAL-TIME SCORE ACCUMULATION
# ==========================================
with st.sidebar:
    st.image("https://www.thebluerock.com.au/wp-content/themes/bluerock/assets/img/bluerock-logo.svg", width=150)
    st.markdown("### 📊 AI Readiness Pillars")
    st.caption("Live Signal Accumulation Engine")
    st.write("---")
    
    for pillar, score in st.session_state.pillar_scores.items():
        st.write(f"**{pillar}**")
        st.progress(score / 100.0, text=f"{score}/100")
    
    st.write("---")
    if st.button("🔄 Reset Assessment", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==========================================
# 5. MAIN CHAT INTERFACE
# ==========================================
st.title("🤖 AI Readiness Roadmap Agent")
st.caption("Proof of Concept: Dynamic Branching & Real-time Scoring")

for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Matikan input chat jika asesmen sudah selesai
if st.session_state.assessment_complete:
    st.success("✅ Assessment Complete! In production, this will trigger the n8n webhook to generate the PDF and log the prospect into the CRM.")
else:
    if prompt := st.chat_input("Enter your response..."):
        st.session_state.display_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
            
        st.session_state.chat_history.append({"role": "user", "parts": [prompt]})
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing signals..."):
                try:
                    response = model.generate_content(
                        st.session_state.chat_history,
                        generation_config=genai.GenerationConfig(
                            response_mime_type="application/json"
                        )
                    )
                    raw_text = response.text.strip()
                    parsed_data = json.loads(raw_text, strict=False)
                    
                    agent_reply = parsed_data.get("agent_reply", "I'm sorry, I couldn't process that.")
                    new_scores = parsed_data.get("current_scores", st.session_state.pillar_scores)
                    
                    st.write(agent_reply)
                    st.session_state.display_messages.append({"role": "assistant", "content": agent_reply})
                    st.session_state.chat_history.append({"role": "model", "parts": [raw_text]})
                    st.session_state.pillar_scores = new_scores
                    
                    # Cek apakah AI memutuskan untuk berhenti
                    if "generating your personalized AI Readiness Roadmap now" in agent_reply:
                        st.session_state.assessment_complete = True
                        
                    st.rerun()
                    
                except json.JSONDecodeError:
                    st.error("Engine Error: Invalid JSON response. The LLM encountered an edge case.")
                    print(f"RAW: {raw_text}")
                except Exception as e:
                    st.error(f"Engine Error: {e}")