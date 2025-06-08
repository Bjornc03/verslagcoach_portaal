import streamlit as st
import openai
import docx
import pdfplumber
import tempfile
import os
import math
import requests
from docx.shared import RGBColor
from difflib import SequenceMatcher

openai.api_key = st.secrets["OPENAI_API_KEY"]

# ========== ZeroGPT Business API ===========

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

def check_plagiarism_zerogpt_v2(text, api_key):
    url = "https://api.zerogpt.com/v2/plagiarism/detect"
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

# ========== Tekst extractie en splitsen ===========

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

# ========== Taalcontrole / Schrijfstijl-blokken ===========

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

# ======= Highlight-functie (fuzzy) =======
def fuzzy_highlight_docx(orig_docx_path, highlight_sentences, highlight_color=7):
    doc = docx.Document(orig_docx_path)
    sentences_left = set(highlight_sentences)
    not_found = set()
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

# ======= Rapport-generatie: alles-in-één =======
def maak_gecombineerd_word(
        totaal_beoordeling,
        all_fouten,
        ai_result=None,
        ai_sentences=None,
        ai_not_found=None,
        plag_result=None,
        plag_sentences=None,
        plag_not_found=None,
        orig_docx_path=None):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc = docx.Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = docx.shared.Pt(11)
    doc.add_heading("AI Feedback – Volledig Rapport", 0)

    # ---- Taalcontrole ----
    if totaal_beoordeling or all_fouten:
        doc.add_heading("Taalcontrole & schrijfkwaliteit", level=1)
        disclaimer = ("Deze controle richt zich op grammatica, spelling en schrijfstijl. "
                      "AI-adviezen zijn een hulpmiddel, geen eindbeoordeling.")
        doc.add_paragraph(disclaimer)
        if totaal_beoordeling:
            doc.add_heading("Beoordeling schrijfkwaliteit", level=2)
            for line in totaal_beoordeling.split('\n'):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                doc.add_paragraph(line)
        if all_fouten:
            doc.add_heading("Fouten per hoofdstuk en paragraaf", level=2)
            for fouten in all_fouten:
                current_kopje = None
                for line in fouten.split('\n'):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.lower().startswith("hoofdstuk") or line.lower().startswith("kopje"):
                        kopje_naam = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                        current_kopje = kopje_naam
                        doc.add_heading(f"Hoofdstuk/Kopje: {kopje_naam}", level=3)
                    elif line.startswith("- Originele zin:"):
                        doc.add_paragraph(line, style="List Bullet")
                    elif line.startswith("- Verbeterde zin:"):
                        doc.add_paragraph(line, style="List Bullet")
                    elif line.startswith("- Uitleg:"):
                        doc.add_paragraph(line, style="List Bullet")
                    else:
                        doc.add_paragraph(line)
                doc.add_paragraph("")

    # ---- AI-Detectie ----
    if ai_result is not None:
        doc.add_page_break()
        doc.add_heading("AI-detectie (ZeroGPT)", level=1)
        disclaimer = ("Let op: deze detectie is een hulpmiddel, geen bewijs. "
                      "AI-score en verdachte zinnen zijn indicatief. Controleer altijd zelf.")
        doc.add_paragraph(disclaimer)
        summary = (
            f"AI-score: {ai_result.get('score', 'onbekend')}%\n"
            f"Resultaat: {ai_result.get('verdict', 'onbekend')}\n"
            f"Aantal verdachte zinnen: {len(ai_sentences) if ai_sentences else 0}"
        )
        doc.add_paragraph(summary)
        if orig_docx_path and ai_sentences:
            doc.add_heading("AI-verdachte tekst (geel gemarkeerd in originele tekst hieronder):", level=2)
            temp_ai, _ = fuzzy_highlight_docx(orig_docx_path, ai_sentences, highlight_color=7)
            ai_doc = docx.Document(temp_ai)
            for para in ai_doc.paragraphs:
                p = doc.add_paragraph()
                for run in para.runs:
                    r = p.add_run(run.text)
                    if run.font.highlight_color:
                        r.font.highlight_color = run.font.highlight_color
            os.remove(temp_ai)
        if ai_not_found:
            doc.add_paragraph("")
            doc.add_paragraph("Verdachte zinnen die niet automatisch gemarkeerd konden worden:", style="Intense Quote")
            for nf in ai_not_found:
                doc.add_paragraph(nf)

    # ---- Plagiaatcontrole ----
    if plag_result is not None:
        doc.add_page_break()
        doc.add_heading("Plagiaatcontrole (ZeroGPT)", level=1)
        disclaimer = ("Let op: deze plagiaatcontrole is een eerste indicatie en géén vervanging van professionele plagiaatscans zoals Turnitin of Scribbr.")
        doc.add_paragraph(disclaimer)
        summary = (
            f"Plagiaat-percentage: {plag_result.get('score', 'onbekend')}%\n"
            f"Resultaat: {plag_result.get('verdict', 'onbekend')}\n"
            f"Aantal verdachte zinnen: {len(plag_sentences) if plag_sentences else 0}"
        )
        doc.add_paragraph(summary)
        if orig_docx_path and plag_sentences:
            doc.add_heading("Plagiaatverdachte tekst (geel gemarkeerd in originele tekst hieronder):", level=2)
            temp_pl, _ = fuzzy_highlight_docx(orig_docx_path, plag_sentences, highlight_color=7)
            pl_doc = docx.Document(temp_pl)
            for para in pl_doc.paragraphs:
                p = doc.add_paragraph()
                for run in para.runs:
                    r = p.add_run(run.text)
                    if run.font.highlight_color:
                        r.font.highlight_color = run.font.highlight_color
            os.remove(temp_pl)
        if plag_not_found:
            doc.add_paragraph("")
            doc.add_paragraph("Plagiaatzinnen die niet automatisch gemarkeerd konden worden:", style="Intense Quote")
            for nf in plag_not_found:
                doc.add_paragraph(nf)
    doc.save(temp.name)
    return temp.name

# =============== STREAMLIT INTERFACE ================

st.title("Verslagcoach – Alles-in-één Controle (ZeroGPT Business)")
st.write("Upload je verslag (.docx of .pdf), kies gewenste controles en ontvang één gecombineerd, professioneel Word-rapport (in Arial) met taalfouten, AI- en/of plagiaatmarkering en heldere samenvattingen.")

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
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        if file.name.endswith(".docx"):
            file.seek(0)
            temp_input.write(file.read())
            temp_input.flush()
            verslag_tekst = extract_text_from_docx(temp_input.name)
        elif file.name.endswith(".pdf"):
            verslag_tekst = extract_text_from_pdf(file)
        else:
            st.error("Bestandstype niet ondersteund.")
            verslag_tekst = ""
        temp_input.close()

        if not verslag_tekst or len(verslag_tekst.strip()) < 50:
            st.error("Kon geen bruikbare tekst vinden in het bestand. Probeer een ander document.")
        else:
            totaal_beoordeling = ""
            all_fouten = []
            ai_result = None
            ai_sentences = []
            ai_not_found = []
            plag_result = None
            plag_sentences = []
            plag_not_found = []

            # ---- Taalcontrole & schrijfkwaliteit ----
            if "Taalcontrole & schrijfkwaliteit" in diensten:
                st.info("Taalcontrole wordt uitgevoerd...")
                chunks = split_text_into_chunks(verslag_tekst, max_words=2000, overlap_words=100)
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

            # ---- AI-DETECTIE ----
            if "AI-detectie" in diensten:
                st.info("AI-detectie wordt uitgevoerd...")
                try:
                    zgt_api_key = st.secrets["ZEROGPT_API_KEY"]
                    status, ai_resp = detect_ai_zerogpt_v2(verslag_tekst[:400000], zgt_api_key)
                    st.write("ZeroGPT AI detectie response:", ai_resp)  # DEBUG
                    if status == 200 and ai_resp.get("ai_sentences"):
                        ai_result = ai_resp
                        ai_sentences = ai_resp["ai_sentences"]
                        _, ai_not_found = fuzzy_highlight_docx(temp_input.name, ai_sentences, highlight_color=7)
                    else:
                        ai_result = ai_resp
                        ai_sentences = []
                        ai_not_found = []
                        st.warning("ZeroGPT AI-detectie retourneerde geen verdachte zinnen.")
                except Exception as e:
                    st.error(f"Fout bij ZeroGPT AI-detectie: {e}")

            # ---- PLAGIAAT ----
            if "Plagiaatcontrole" in diensten:
                st.info("Plagiaatcontrole wordt uitgevoerd...")
                try:
                    zgt_api_key = st.secrets["ZEROGPT_API_KEY"]
                    status, plag_resp = check_plagiarism_zerogpt_v2(verslag_tekst[:400000], zgt_api_key)
                    st.write("ZeroGPT plagiaat response:", plag_resp)  # DEBUG
                    if status == 200 and plag_resp.get("plagiarized_sentences"):
                        plag_result = plag_resp
                        plag_sentences = plag_resp["plagiarized_sentences"]
                        _, plag_not_found = fuzzy_highlight_docx(temp_input.name, plag_sentences, highlight_color=7)
                    else:
                        plag_result = plag_resp
                        plag_sentences = []
                        plag_not_found = []
                        st.warning("ZeroGPT plagiaatcontrole retourneerde geen verdachte zinnen.")
                except Exception as e:
                    st.error(f"Fout bij ZeroGPT plagiaatcontrole: {e}")

            # ---- Alles in één Word-rapport ----
            report_path = maak_gecombineerd_word(
                totaal_beoordeling=totaal_beoordeling,
                all_fouten=all_fouten,
                ai_result=ai_result,
                ai_sentences=ai_sentences,
                ai_not_found=ai_not_found,
                plag_result=plag_result,
                plag_sentences=plag_sentences,
                plag_not_found=plag_not_found,
                orig_docx_path=temp_input.name
            )
            with open(report_path, "rb") as f:
                st.success("Download hieronder je complete feedbackrapport:")
                st.download_button(
                    label="Download volledig rapport (.docx)",
                    data=f.read(),
                    file_name="AI-feedback-volledig-rapport.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            os.remove(report_path)

        if os.path.exists(temp_input.name):
            os.remove(temp_input.name)
