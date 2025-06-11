import streamlit as st
import docx
import requests
import tempfile
import os

ZEROGPT_API_KEY = st.secrets["ZEROGPT_API_KEY"]

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def detect_ai_zerogpt(text, api_key):
    url = "https://api.zerogpt.com/api/v2/detect/text"
    payload = {
        "input_text": text,
        "language": "auto"
    }
    headers = {
        "accept": "application/json",
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code, response.json()

st.title("ZeroGPT AI-detectie (officiële API, 2024)")
file = st.file_uploader("Upload een .docx-bestand", type=["docx"])

if st.button("Start AI-detectie"):
    if not file:
        st.error("Upload eerst een .docx-bestand!")
    else:
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        file.seek(0)
        temp_input.write(file.read())
        temp_input.flush()
        verslag_tekst = extract_text_from_docx(temp_input.name)
        temp_input.close()

        st.info("AI-detectie uitvoeren via ZeroGPT...")
        status, result = detect_ai_zerogpt(verslag_tekst[:40000], ZEROGPT_API_KEY)
        st.write("ZeroGPT API response:", result)  # Debug-output

        if status == 200:
            st.success("Detectie gelukt!")
            st.markdown(f"**AI Percentage:** {result.get('ai_probability', 'onbekend')}%")
            st.markdown(f"**Resultaat:** {result.get('result', 'onbekend')}")
            st.markdown(f"**AI Verdict:** {result.get('verdict', 'onbekend')}")
            if result.get("ai_sentences"):
                st.markdown(f"**Aantal verdachte zinnen:** {len(result['ai_sentences'])}")
                st.write("Verdachte zinnen:", result["ai_sentences"])
            else:
                st.info("Geen verdachte zinnen gevonden.")
        else:
            st.error(f"Fout bij ZeroGPT: {result}")
        os.remove(temp_input.name)
