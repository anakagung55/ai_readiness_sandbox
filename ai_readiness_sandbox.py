import requests
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
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
if "assessment_complete" not in st.session_state:
    st.session_state.assessment_complete = False

# Tambahkan baris ini untuk menyimpan email user
if "user_email" not in st.session_state:
    st.session_state.user_email = None

# ==========================================
# 3.5. EMAIL GATE / LOGIN SCREEN
# ==========================================
if not st.session_state.user_email:
    # Bikin tampilan agak ke tengah biar rapi
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRwfocMaLYiwVSGhGc8mb7SjZ6uGzlcDHU62w&s", width=200)
        st.markdown("## AI Readiness Diagnostic")
        st.write("Discover your organisation's AI maturity across 6 key pillars. Please enter your work email to begin the assessment.")
        
        with st.form("login_form"):
            email_input = st.text_input("Work Email Address", placeholder="name@company.com")
            submit_button = st.form_submit_button("Start Assessment", use_container_width=True)
            
            if submit_button:
                # Validasi email sederhana pakai regex (lu udah import 're' di atas)
                if email_input and re.match(r"[^@]+@[^@]+\.[^@]+", email_input):
                    st.session_state.user_email = email_input
                    st.rerun() # Refresh halaman untuk menghilangkan form login
                else:
                    st.error("⚠️ Please enter a valid email address to proceed.")
                    
    # st.stop() adalah KUNCI. Ini menghentikan eksekusi kode di bawahnya
    # sehingga Sidebar dan Chat UI tidak akan dirender sampai st.stop() ini dilewati.
    st.stop()

# ==========================================
# 4. SIDEBAR: REAL-TIME SCORE ACCUMULATION
# ==========================================
with st.sidebar:
    st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRwfocMaLYiwVSGhGc8mb7SjZ6uGzlcDHU62w&s", width=150)
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
    st.success("✅ Assessment Complete! Generating your custom roadmap...")
    
    # LOGIC UNTUK NGE-SAVE KE GOOGLE SHEETS
    if "logged_to_db" not in st.session_state:
        with st.spinner("Saving results to BlueRock Database..."):
            try:
                # 1. Panggil koneksi ke Google Sheets
                conn = st.connection("gsheets", type=GSheetsConnection)
                
                # 2. Siapkan URL Google Sheet lu (Ganti dengan URL file "BlueRock AI POC Logs" milik lu)
                SHEET_URL = "https://docs.google.com/spreadsheets/d/1NUyjSYvtvrlcWoFMXUg4_dxZHoEmyJmpjBk1nq4WV-M/edit"
                
                # 3. Rangkum history chat jadi satu teks panjang
                transcript = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.display_messages])
                
                # 4. Susun data baru yang mau di-insert
                scores = st.session_state.pillar_scores
                new_data = pd.DataFrame([{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Email": st.session_state.user_email,
                    "Score_Strategy": scores.get("Strategy & Vision", 0),
                    "Score_Data": scores.get("Data Maturity", 0),
                    "Score_Tech": scores.get("Technical Infrastructure", 0),
                    "Score_Talent": scores.get("Talent & Skills", 0),
                    "Score_Gov": scores.get("Governance & Risk", 0),
                    "Score_Culture": scores.get("Culture & Adoption", 0),
                    "Chat_Transcript": transcript
                }])
                
                # 5. Baca data lama, gabung sama data baru, lalu timpa balik ke Sheets
                existing_data = conn.read(spreadsheet=SHEET_URL, usecols=list(range(9)))
                updated_data = pd.concat([existing_data, new_data], ignore_index=True)
                conn.update(spreadsheet=SHEET_URL, data=updated_data)
                
                # Tandai biar nggak nge-save double kalau layar kereload
                st.session_state.logged_to_db = True
                st.success("📝 All diagnostic data successfully logged to database. Safe to close this window.")
                try:
                    webhook_url = "https://agungajus02.app.n8n.cloud/webhook-test/c0c19033-bf10-44fe-a606-7ad7e0df795a"
                    payload = {
                        "email": st.session_state.user_email,
                        "scores": st.session_state.pillar_scores,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    requests.post(webhook_url, json=payload)
                    st.info("🚀 Data sent to automation engine for PDF generation!")
                except Exception as e:
                    st.error(f"Webhook Error: {e}")
            except Exception as e:
                st.error(f"Database Error: Failed to save logs. {e}")
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