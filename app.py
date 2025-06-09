import streamlit as st
import openai
import docx
import pdfplumber
import tempfile
import os
import math
import requests

openai.api_key = st.secrets["OPENAI_API_KEY"]

# Functie om het rapport via Make-webhook te mailen
def stuur_mail_make_webhook(webhook_url, email, file_path):
    with open(file_path, "rb") as f:
        file_content = f.read()
    files = {
        'file': (
            'AI-feedback-schrijftaal.docx',
            file_content,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    }
    data = {'email': email}
    response = requests.post(webhook_url, data=data, files=files)
    return response.status_code, response.text

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    return text

def split_text_into_chunks(text, max_words=2000, overlap_words=100):
    words = text.split()
    num_chunks = math.ceil(len(words) / max_words)
    chunks = []
    for i in range(num_chunks):
        start = max(0, i * max_words - i * overlap_words)
        end = min(len(words), (i+1) * max_words)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
    return chunks

def prompt_beoordeling(tekst):
    return f"""
Je bent een ervaren HBO-taal- en scriptiebeoordelaar.
Geef GEEN inhoudelijke samenvatting, maar alleen een **kritische beoordeling** (max 300 woorden) over de **kwaliteit van het schrijven van het hele rapportdeel**: spelling, grammatica, consistentie, helderheid, opbouw, rode draad, argumentatie, bronvermelding. Benoem sterke en zwakke punten van het schrijfwerk en geef een kort eindoordeel. Vat NIET de inhoud samen.

Daarna:
- Rapporteer **alleen echte taalfouten of grammaticale/spelfouten**, géén stijlverbeteringen.
- Voor iedere fout:
  - Noteer het hoofdstuk/kopje zoals dat letterlijk in de tekst staat, of schrijf 'niet gevonden' als het ontbreekt.
  - Noem de originele zin met fout.
  - Geef de verbeterde zin.
  - Korte uitleg (max 1 zin) waarom het fout is.
- Rapporteer GEEN fouten als er geen taalfouten zijn in een kopje/hoofdstuk/paragraaf.

**Structuur van de feedback:**

# Beoordeling schrijfkwaliteit

# Fouten per hoofdstuk en paragraaf

Hoofdstuk/Kopje: [exact of 'niet gevonden']
- Originele zin: ...
- Verbeterde zin: ...
- Uitleg: ...

(herhaal dit voor elke gevonden fout)

Hier is de tekst:
\"\"\"
{tekst}
\"\"\"
"""

def prompt_alleen_fouten(tekst):
    return f"""
Je bent een ervaren HBO-taal- en scriptiebeoordelaar.

- Rapporteer **alleen echte taalfouten of grammaticale/spelfouten**, géén stijlverbeteringen.
- Voor iedere fout:
  - Noteer het hoofdstuk/kopje zoals dat letterlijk in de tekst staat, of schrijf 'niet gevonden' als het ontbreekt.
  - Noem de originele zin met fout.
  - Geef de verbeterde zin.
  - Korte uitleg (max 1 zin) waarom het fout is.
- Rapporteer GEEN fouten als er geen taalfouten zijn in een kopje/hoofdstuk/paragraaf.

**Structuur van de feedback:**

# Fouten per hoofdstuk en paragraaf

Hoofdstuk/Kopje: [exact of 'niet gevonden']
- Originele zin: ...
- Verbeterde zin: ...
- Uitleg: ...

(herhaal dit voor elke gevonden fout)

Hier is de tekst:
\"\"\"
{tekst}
\"\"\"
"""

def maak_feedback_docx(totaal_beoordeling, all_fouten):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc = docx.Document()
    # Arial standaard
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = docx.shared.Pt(11)

    doc.add_heading("AI Feedback – Schrijfkwaliteit & Taalcontrole", 0)
    h1 = doc.add_heading("Beoordeling schrijfkwaliteit", level=1)
    h1.alignment = 0
    for line in totaal_beoordeling.split('\n'):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = doc.add_paragraph(line)
        p.style.font.name = 'Arial'
        p.style.font.size = docx.shared.Pt(11)
    h2 = doc.add_heading("Fouten per hoofdstuk en paragraaf", level=1)
    h2.alignment = 0
    for fouten in all_fouten:
        current_kopje = None
        for line in fouten.split('\n'):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("hoofdstuk") or line.lower().startswith("kopje"):
                kopje_naam = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                current_kopje = kopje_naam
                h_kopje = doc.add_heading(f"Hoofdstuk/Kopje: {kopje_naam}", level=2)
                h_kopje.alignment = 0
            elif line.startswith("- Originele zin:"):
                p = doc.add_paragraph(line, style="List Bullet")
                p.style.font.name = 'Arial'
            elif line.startswith("- Verbeterde zin:"):
                p = doc.add_paragraph(line, style="List Bullet")
                p.style.font.name = 'Arial'
            elif line.startswith("- Uitleg:"):
                p = doc.add_paragraph(line, style="List Bullet")
                p.style.font.name = 'Arial'
            else:
                p = doc.add_paragraph(line)
                p.style.font.name = 'Arial'
        doc.add_paragraph("")  # witregel tussen segmenten
    doc.save(temp.name)
    return temp.name

st.title("Verslagcoach – Schrijfstijl & Taalcontrole")
st.write("Upload je verslag (.docx of .pdf). Je ontvangt een Word-bestand in Arial met een beoordeling van het schrijfwerk en fouten per hoofdstuk/paragraaf, inclusief kopjes waar mogelijk.")

email = st.text_input("Vul je e-mailadres in (optioneel):")
file = st.file_uploader("Upload je verslag (.docx of .pdf)", type=["docx", "pdf"])

if st.button("Verzenden"):
    if not file:
        st.error("Upload een bestand!")
    else:
        if file.name.endswith(".docx"):
            file.seek(0)
            verslag_tekst = extract_text_from_docx(file)
        elif file.name.endswith(".pdf"):
            verslag_tekst = extract_text_from_pdf(file)
        else:
            st.error("Bestandstype niet ondersteund.")
            verslag_tekst = ""

        if not verslag_tekst or len(verslag_tekst.strip()) < 50:
            st.error("Kon geen bruikbare tekst vinden in het bestand. Probeer een ander document.")
        else:
            chunks = split_text_into_chunks(verslag_tekst, max_words=2000, overlap_words=100)
            all_fouten = []
            totaal_beoordeling = ""
            for i, chunk in enumerate(chunks, start=1):
                st.info(f"AI verwerkt deel {i} van {len(chunks)}...")
                if i == 1:
                    prompt = prompt_beoordeling(chunk)
                else:
                    prompt = prompt_alleen_fouten(chunk)
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                    )
                    feedback = response.choices[0].message.content
                    if i == 1:
                        split_idx = feedback.lower().find("# fouten per hoofdstuk")
                        if split_idx > 0:
                            totaal_beoordeling = feedback[:split_idx]
                            all_fouten.append(feedback[split_idx:])
                        else:
                            totaal_beoordeling = feedback
                    else:
                        all_fouten.append(feedback)
                except Exception as e:
                    st.error(f"Fout bij AI-verwerking van deel {i}: {e}")
                    if i == 1:
                        totaal_beoordeling = "[AI-verwerking van beoordeling mislukt]"
                    else:
                        all_fouten.append(f"[AI-verwerking mislukt voor deel {i}]")

            docx_path = maak_feedback_docx(totaal_beoordeling, all_fouten)
            with open(docx_path, "rb") as f:
                st.success("Download hieronder je AI-feedback als Word-bestand:")
                st.download_button(
                    label="Download feedback (.docx)",
                    data=f.read(),
                    file_name="AI-feedback-schrijftaal.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            # Automatisch mailen als e-mailadres is ingevuld
            if email and len(email) > 5:
                webhook_url = "https://hook.eu2.make.com/q5yuw6u91lttvulnj1vdg8m0csyibkcy"
                status, resp = stuur_mail_make_webhook(webhook_url, email, docx_path)
                if status == 200:
                    st.success("E-mail is verzonden via Make!")
                else:
                    st.warning(f"E-mail via Make is niet gelukt: {resp}")

            os.remove(docx_path)
