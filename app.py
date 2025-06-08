import streamlit as st
import openai
import docx
import pdfplumber
import tempfile
import os
import math
import requests
from docx.shared import RGBColor

openai.api_key = st.secrets["OPENAI_API_KEY"]

# ================== ZeroGPT API FUNCTIES ==================

def detect_ai_zerogpt(text, api_key):
    url = "https://api.zerogpt.com/api/v1/detect"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    data = {
        "input_text": text,
        "language": "auto"
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.text}

def check_plagiarism_zerogpt(text, api_key):
    url = "https://api.zerogpt.com/api/v1/plagiarism"
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    data = {
        "input_text": text,
        "language": "auto"
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.text}

# =============== Tekst extractie en splitsen ===============

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

# =========== HUIDIGE SCHRIJFSTIJL/TAALCONTROLE BLOKKEN ===========

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

# ============ AI- EN PLAGIAAT HIGHLIGHT WORD-BESTANDEN =============

def highlight_sentences_in_docx(orig_docx_path, highlight_sentences, filename="AI-verdacht.docx", highlight_color=RGBColor(255,255,0)):
    # highlight_sentences: lijst van string-zinnen die gemarkeerd moeten worden
    # LET OP: Matching is op letterlijke string. Kan bij complexe/verschoven zinnen minder werken.
    doc = docx.Document(orig_docx_path)
    for para in doc.paragraphs:
        for sent in highlight_sentences:
            if sent and sent.strip() and sent.strip() in para.text:
                inline = para.runs
                for i in range(len(inline)):
                    if sent.strip() in inline[i].text:
                        # Highlight volledige run
                        inline[i].font.highlight_color = 7  # geel (Word code 7)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(temp.name)
    return temp.name

# =============== STREAMLIT INTERFACE ================

st.title("Verslagcoach – Meerdere controles")
st.write("Upload je verslag (.docx of .pdf). Kies zelf welke controles je wilt uitvoeren. Je krijgt voor elke dienst een los Word-bestand.")

diensten = st.multiselect(
    "Welke controles wil je uitvoeren?",
    [
        "Taalcontrole & schrijfkwaliteit",
        "AI-detectie",
        "Plagiaatcontrole"
    ],
    default=["Taalcontrole & schrijfkwaliteit"]
)

email = st.text_input("Vul je e-mailadres in (optioneel):")
file = st.file_uploader("Upload je verslag (.docx of .pdf)", type=["docx", "pdf"])

if st.button("Verzenden"):
    if not file:
        st.error("Upload een bestand!")
    else:
        # Bestand opslaan tbv highlighting
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        if file.name.endswith(".docx"):
            file.seek(0)
            temp_input.write(file.read())
            temp_input.flush()
            verslag_tekst = extract_text_from_docx(temp_input.name)
        elif file.name.endswith(".pdf"):
            verslag_tekst = extract_text_from_pdf(file)
            # Optioneel: PDF omzetten naar docx als gebruiker AI/Plagiaat wil
        else:
            st.error("Bestandstype niet ondersteund.")
            verslag_tekst = ""
        temp_input.close()

        if not verslag_tekst or len(verslag_tekst.strip()) < 50:
            st.error("Kon geen bruikbare tekst vinden in het bestand. Probeer een ander document.")
        else:
            # ---- Taalcontrole & schrijfkwaliteit ----
            if "Taalcontrole & schrijfkwaliteit" in diensten:
                st.info("Taalcontrole wordt uitgevoerd...")
                chunks = split_text_into_chunks(verslag_tekst, max_words=2000, overlap_words=100)
                all_fouten = []
                totaal_beoordeling = ""
                for i, chunk in enumerate(chunks, start=1):
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
                    st.success("Download hieronder je AI-feedback als Word-bestand (taalcontrole):")
                    st.download_button(
                        label="Download taalcontrole (.docx)",
                        data=f.read(),
                        file_name="AI-feedback-schrijftaal.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                os.remove(docx_path)

            # ---- AI-DETECTIE ----
            if "AI-detectie" in diensten:
                st.info("AI-detectie wordt uitgevoerd...")
                try:
                    zgt_api_key = st.secrets["ZEROGPT_API_KEY"]
                    ai_result = detect_ai_zerogpt(verslag_tekst[:10000], zgt_api_key)  # ZeroGPT limiet!
                    # NB: 'details' bevat meestal lijst van verdachte zinnen in 'ai_sentences'
                    ai_sentences = []
                    if "ai_sentences" in ai_result:
                        ai_sentences = ai_result["ai_sentences"]
                    elif "details" in ai_result and isinstance(ai_result["details"], dict) and "ai_sentences" in ai_result["details"]:
                        ai_sentences = ai_result["details"]["ai_sentences"]
                    if not ai_sentences:
                        st.warning("Geen AI-zinnen gemarkeerd door ZeroGPT.")
                    docx_highlighted = highlight_sentences_in_docx(temp_input.name, ai_sentences, filename="AI-verdacht.docx")
                    with open(docx_highlighted, "rb") as f:
                        st.success("Download hieronder het Word-bestand met AI-verdachte tekst geel gemarkeerd:")
                        st.download_button(
                            label="Download AI-detectie (.docx)",
                            data=f.read(),
                            file_name="AI-detectie-rapport.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    os.remove(docx_highlighted)
                except Exception as e:
                    st.error(f"Fout bij ZeroGPT AI-detectie: {e}")

            # ---- PLAGIAAT ----
            if "Plagiaatcontrole" in diensten:
                st.info("Plagiaatcontrole wordt uitgevoerd...")
                try:
                    zgt_api_key = st.secrets["ZEROGPT_API_KEY"]
                    pl_result = check_plagiarism_zerogpt(verslag_tekst[:10000], zgt_api_key)
                    plag_sentences = []
                    if "plagiarized_sentences" in pl_result:
                        plag_sentences = pl_result["plagiarized_sentences"]
                    elif "details" in pl_result and isinstance(pl_result["details"], dict) and "plagiarized_sentences" in pl_result["details"]:
                        plag_sentences = pl_result["details"]["plagiarized_sentences"]
                    if not plag_sentences:
                        st.warning("Geen plagiaatzinnen gemarkeerd door ZeroGPT.")
                    docx_highlighted = highlight_sentences_in_docx(temp_input.name, plag_sentences, filename="Plagiaat-verdacht.docx")
                    with open(docx_highlighted, "rb") as f:
                        st.success("Download hieronder het Word-bestand met plagiaat-verdachte tekst geel gemarkeerd:")
                        st.download_button(
                            label="Download plagiaatrapport (.docx)",
                            data=f.read(),
                            file_name="Plagiaatcontrole-rapport.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    os.remove(docx_highlighted)
                except Exception as e:
                    st.error(f"Fout bij ZeroGPT plagiaatcontrole: {e}")

        # Opruimen
        if os.path.exists(temp_input.name):
            os.remove(temp_input.name)
