import streamlit as st
import openai
import tempfile
import os
import docx
import fitz  # PyMuPDF
import win32com.client as win32
from docx import Document

openai.api_key = st.secrets["OPENAI_API_KEY"]

def extract_text(file):
    ext = file.name.split('.')[-1].lower()
    if ext == "pdf":
        return extract_text_from_pdf(file)
    elif ext == "docx":
        return extract_text_from_docx(file)
    else:
        return None

def extract_text_from_pdf(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    text = ""
    with fitz.open(tmp_path) as doc:
        for page in doc:
            text += page.get_text()
    os.remove(tmp_path)
    return text

def extract_text_from_docx(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    doc = Document(tmp_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    os.remove(tmp_path)
    return text

def generate_feedback(text, onderwerp, niveau):
    prompt = f"""
Je bent een professionele verslagcoach. Geef inhoudelijke feedback op het onderstaande verslag. 

<verslaginformatie>
  <onderwerp>{onderwerp}</onderwerp>
  <niveau>{niveau}</niveau>
</verslaginformatie>

Beoordeel de volgende onderdelen:
- Structuur en opbouw
- Inhoudelijke diepgang passend bij {niveau}
- Logica en argumentatie
- Taalgebruik en grammaticale correctheid
- Bronvermelding en APA-stijl (indien van toepassing)

Gebruik een professionele, duidelijke schrijfstijl. Geef de feedback puntsgewijs en waar mogelijk met concrete voorbeelden.

Verslagtekst:
{text}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Je bent een ervaren verslagcoach."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    return response["choices"][0]["message"]["content"]

def save_feedback_as_docx(feedback_text, student_name):
    doc = Document()
    doc.add_heading(f"Verslagfeedback – {student_name}", level=1)
    for line in feedback_text.split("\n"):
        doc.add_paragraph(line)
    temp_path = tempfile.mktemp(suffix=".docx")
    doc.save(temp_path)
    return temp_path

def send_email_with_feedback(email, naam, feedback_path):
    outlook = win32.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.To = email
    mail.Subject = "Feedback op je verslag"
    mail.Body = f"Beste {naam},\n\nIn de bijlage vind je de feedback op je verslag.\n\nMet vriendelijke groet,\nVerslagcoach AI"
    mail.Attachments.Add(feedback_path)
    mail.Send()

# --- Streamlit interface ---
st.title("Verslagcoach Uploadportaal")
st.write("Upload hier je verslag en ontvang gerichte feedback per e-mail.")

with st.form("upload_form"):
    naam = st.text_input("Je naam")
    email = st.text_input("Je e-mailadres")
    onderwerp = st.text_input("Waar gaat je verslag over?")
    niveau = st.selectbox("Opleidingsniveau", ["MBO", "HBO", "Universitair"])
    file = st.file_uploader("Upload je verslag (.docx of .pdf)", type=["docx", "pdf"])
    submitted = st.form_submit_button("Verstuur")

if submitted:
    if not all([naam, email, onderwerp, niveau, file]):
        st.warning("Vul alle velden in en upload een bestand.")
    else:
        with st.spinner("Bezig met verwerken..."):
            verslagtekst = extract_text(file)
            if not verslagtekst:
                st.error("Kon geen tekst extraheren uit het bestand.")
            else:
                feedback = generate_feedback(verslagtekst, onderwerp, niveau)
                feedback_path = save_feedback_as_docx(feedback, naam)
                send_email_with_feedback(email, naam, feedback_path)
                st.success("Feedback is verstuurd naar je e-mailadres.")
