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
# Kita pakai Gemini 1.5 Flash karena butuh respons super cepat untuk chat
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 2. THE MASTER SYSTEM PROMPT (THOMAS'S LOGIC)
# ==========================================
SYSTEM_PROMPT = """
You are the BlueRock AI Readiness Consultant, an expert conversational agent.
Your objective is to conduct a dynamic ~15 question assessment to determine a company's AI Readiness across 6 pillars.

THE 6 PILLARS (Score 0-100):
1. Strategy & Vision
2. Data Maturity
3. Technical Infrastructure
4. Talent & Skills
5. Governance & Risk
6. Culture & Adoption

YOUR INSTRUCTIONS:
1. Start by asking Tier 1 context: Company industry, size, and current AI engagement (Exploring, Piloting, Production, or Core).
2. ADAPTIVE DEPTH: Based on their answers, branch your questions. If they are 'Exploring', ask about budget and leadership. If 'Production', ask about MLOps, model drift, and governance.
3. CONTRADICTION DETECTION: If they say "AI is core" but later reveal "data is in spreadsheets", politely challenge them.
4. TONE: Professional, consultative, and concise. Ask ONE question at a time. Do not overwhelm the user.

CRITICAL OUTPUT FORMAT:
You MUST respond strictly in the following JSON format for every single turn. Do not add markdown outside the JSON.
{
  "agent_reply": "Your conversational response and next question here...",
  "current_scores": {
    "Strategy & Vision": 10,
    "Data Maturity": 20,
    "Technical Infrastructure": 15,
    "Talent & Skills": 5,
    "Governance & Risk": 0,
    "Culture & Adoption": 10
  }
}
Note: Update the scores continuously based on the user's implicit and explicit signals in their answers.
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
        {"role": "assistant", "content": "Hi there! I'm the BlueRock AI Readiness Agent. To get started, could you tell me a bit about your organisation—specifically your industry, approximate headcount, and where you currently stand with AI (e.g., just exploring, running pilots, or already in production)?"}
    ]
if "pillar_scores" not in st.session_state:
    st.session_state.pillar_scores = {
        "Strategy & Vision": 0, "Data Maturity": 0, "Technical Infrastructure": 0,
        "Talent & Skills": 0, "Governance & Risk": 0, "Culture & Adoption": 0
    }

# ==========================================
# 4. SIDEBAR: REAL-TIME SCORE ACCUMULATION
# ==========================================
with st.sidebar:
    st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ_NVia9L0KmXitAE9g_pOv3MoqHsDPv8M7wQ&s", width=150)
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

# Display Chat
for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Handle User Input
if prompt := st.chat_input("Enter your response..."):
    # Add to display
    st.session_state.display_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
        
    # Add to internal history
    st.session_state.chat_history.append({"role": "user", "parts": [prompt]})
    
    # Trigger AI
    with st.chat_message("assistant"):
        with st.spinner("Analyzing signals and adapting logic..."):
            try:
                # KUNCI 1: Paksa API kembalikan format JSON murni
                response = model.generate_content(
                    st.session_state.chat_history,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json"
                    )
                )
                raw_text = response.text.strip()
                
                # KUNCI 2: Pakai strict=False biar aman dari karakter aneh
                parsed_data = json.loads(raw_text, strict=False)
                
                agent_reply = parsed_data.get("agent_reply", "I'm sorry, I couldn't process that.")
                new_scores = parsed_data.get("current_scores", st.session_state.pillar_scores)
                
                # Update State
                st.write(agent_reply)
                st.session_state.display_messages.append({"role": "assistant", "content": agent_reply})
                st.session_state.chat_history.append({"role": "model", "parts": [raw_text]})
                st.session_state.pillar_scores = new_scores
                
                # Rerun to update sidebar
                st.rerun()
                
            except json.JSONDecodeError:
                st.error("Engine Error: Format JSON dari AI tidak valid. Silakan klik Reset Assessment.")
                print(f"RAW FAILED TEXT: {raw_text}")
            except Exception as e:
                st.error(f"Engine Error: {e}")