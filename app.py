import streamlit as st
import docx
import tempfile
import os
import requests
from difflib import SequenceMatcher

def detect_ai_zerogpt_v2(text, api_key):
    url = "https://api.zerogpt.com/v2/detect/text"
    headers = {
        "accept": "application/json",
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "input_text": text,
        "language": "auto"
    }
    response = requests.post(url, headers=headers, json=data)
    return response.status_code, response.json()

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def fuzzy_highlight_docx(orig_docx_path, highlight_sentences, highlight_color=7):
    doc = docx.Document(orig_docx_path)
    sentences_left = set(highlight_sentences)
    for para in doc.paragraphs:
        text = para.text
        if not text.strip():
            continue
        for sent in highlight_sentences:
            ratio = SequenceMatcher(None, sent.strip(), text).ratio()
            if (sent.strip() in text) or (ratio > 0.85 and len(sent.strip()) > 15):
                for run in para.runs:
                    run.font.highlight_color = highlight_color
                if sent in sentences_left:
                    sentences_left.remove(sent)
    not_found = list(sentences_left)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(temp.name)
    return temp.name, not_found

st.title("Losse AI-detectie via ZeroGPT")
file = st.file_uploader("Upload een .docx", type=["docx"])

if st.button("Detecteer AI"):
    if not file:
        st.error("Upload eerst een .docx-bestand")
    else:
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        file.seek(0)
        temp_input.write(file.read())
        temp_input.flush()
        verslag_tekst = extract_text_from_docx(temp_input.name)
        temp_input.close()

        st.info("ZeroGPT AI-detectie wordt uitgevoerd...")
        zgt_api_key = st.secrets["ZEROGPT_API_KEY"]
        status, ai_resp = detect_ai_zerogpt_v2(verslag_tekst[:400000], zgt_api_key)
        st.write("ZeroGPT AI detectie response:", ai_resp)  # DEBUG OUTPUT

        if status == 200 and ai_resp.get("ai_sentences"):
            ai_sentences = ai_resp["ai_sentences"]
            temp_highlight, not_found = fuzzy_highlight_docx(temp_input.name, ai_sentences, highlight_color=7)
            st.success(f"{len(ai_sentences)} verdachte zinnen gemarkeerd!")
            with open(temp_highlight, "rb") as f:
                st.download_button(
                    label="Download AI-detectie (.docx)",
                    data=f.read(),
                    file_name="AI-detectie-rapport.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            if not_found:
                st.warning("Niet alle verdachte zinnen konden gemarkeerd worden.")
        else:
            st.warning("Geen verdachte zinnen gevonden, of ZeroGPT gaf geen resultaat terug.")

        if os.path.exists(temp_input.name):
            os.remove(temp_input.name)
