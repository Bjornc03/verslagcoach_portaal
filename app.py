import streamlit as st
import openai
import docx
import pdfplumber
import tempfile
import os

openai.api_key = st.secrets["OPENAI_API_KEY"]

# ----------- PROMPTS ------------------

def prompt_samenvatting(tekst):
    return f"""
Je bent een ervaren HBO-taal- en scriptiebeoordelaar.
Geef een **kritische beoordeling** (max 300 woorden) van de **schrijfkwaliteit van het hele verslag**: spelling, grammatica, consistentie, helderheid, opbouw, rode draad, argumentatie, bronvermelding. Benoem sterke en zwakke punten van het schrijfwerk en geef een kort eindoordeel. Vat NIET de inhoud samen.
"""

def prompt_segmentatie_taalcontrole(tekst):
    return f"""
Je bent een ervaren HBO-taal- en scriptiebeoordelaar.

Splits de tekst **eerst** in logische segmenten op basis van kopjes, hoofdstukken, paragrafen, genummerde onderdelen (zoals '2.1 Methoden', 'Conclusie', 'Literatuurlijst', etc.).  
Herken je geen duidelijke kopjes? Splits de tekst dan automatisch per ongeveer 1500 woorden.

Voor elk segment:
- Geef het kopje/hoofdstuk (of schrijf 'niet gevonden' als het ontbreekt)
- Rapporteer daarna **alleen echte taalfouten of grammaticale/spelfouten** (géén stijlverbeteringen):
  - De originele zin met fout
  - De verbeterde zin
  - Korte uitleg (max 1 zin) waarom het fout is

**Structuur van de feedback per segment:**

# Segment: [naam kopje of 'niet gevonden']

- Originele zin: ...
- Verbeterde zin: ...
- Uitleg: ...

(herhaal per gevonden fout, sla segmenten zonder fouten over)

Hier is de tekst:
\"\"\"
{tekst}
\"\"\"
"""

# ----------- TEXT EXTRACTIE ---------------

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

# ----------- WORD-GENERATOR ---------------

def maak_feedback_docx(samenvatting, segment_feedback):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc = docx.Document()
    doc.add_heading("AI Feedback – Schrijfkwaliteit & Taalcontrole", 0)

    # Eerst beoordeling schrijfkwaliteit en rode draad
    doc.add_heading("Beoordeling schrijfkwaliteit en rode draad", level=1)
    for line in samenvatting.split('\n'):
        if line.strip():
            doc.add_paragraph(line.strip())

    # Daarna taalfouten per segment
    doc.add_heading("Taalfouten per hoofdstuk/paragraaf", level=1)
    lines = segment_feedback.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("# segment"):
            doc.add_heading(line.replace("# Segment:", "").strip(), level=2)
        elif line.startswith("- Originele zin:"):
            doc.add_paragraph(line, style="List Bullet")
        elif line.startswith("- Verbeterde zin:"):
            doc.add_paragraph(line, style="List Bullet")
        elif line.startswith("- Uitleg:"):
            doc.add_paragraph(line, style="List Bullet")
        else:
            doc.add_paragraph(line)
    doc.save(temp.name)
    return temp.name

# ----------- STREAMLIT INTERFACE ---------------

st.title("Verslagcoach – Schrijfkwaliteit & Taalfouten per Hoofdstuk")
st.write("Upload je verslag (.docx of .pdf). Je ontvangt een Word-bestand met een totale beoordeling van schrijfkwaliteit en rode draad, gevolgd door taalfouten per hoofdstuk/paragraaf.")

email = st.text_input("Vul je e-mailadres in (optioneel):")
file = st.file_uploader("Upload je verslag (.docx of .pdf)", type=["docx", "pdf"])

if st.button("Verzenden"):
    if not file:
        st.error("Upload een bestand!")
    else:
        with st.spinner("Verslag wordt verwerkt en AI-feedback gegenereerd..."):
            try:
                if file.name.endswith(".docx"):
                    verslag_tekst = extract_text_from_docx(file)
                elif file.name.endswith(".pdf"):
                    verslag_tekst = extract_text_from_pdf(file)
                else:
                    st.error("Bestandstype niet ondersteund.")
                    verslag_tekst = ""
            except Exception as e:
                st.error(f"Fout bij openen bestand: {e}")
                verslag_tekst = ""

            if not verslag_tekst or len(verslag_tekst.strip()) < 50:
                st.error("Kon geen bruikbare tekst vinden in het bestand. Probeer een ander document.")
            else:
                try:
                    # Eerst beoordeling (max 4000 woorden voor veiligheid)
                    st.info("AI voert globale beoordeling uit...")
                    samenvatting_resp = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": prompt_samenvatting(verslag_tekst[:4000])}
                        ],
                        temperature=0.2,
                    )
                    samenvatting = samenvatting_resp.choices[0].message.content

                    # Daarna per segment taalfouten
                    st.info("AI voert segmentatie en taalfoutcontrole uit...")
                    segment_resp = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": prompt_segmentatie_taalcontrole(verslag_tekst[:12000])}
                        ],
                        temperature=0.2,
                    )
                    segment_feedback = segment_resp.choices[0].message.content

                    docx_path = maak_feedback_docx(samenvatting, segment_feedback)
                    with open(docx_path, "rb") as f:
                        st.success("Download hieronder je AI-feedback als Word-bestand:")
                        st.download_button(
                            label="Download feedback (.docx)",
                            data=f.read(),
                            file_name="AI-feedback-schrijftaal.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    os.remove(docx_path)

                    st.markdown("**Beoordeling schrijfkwaliteit:**")
                    st.write(samenvatting[:1000] + ("..." if len(samenvatting) > 1000 else ""))

                except Exception as e:
                    st.error(f"Er ging iets mis met de AI-feedback: {e}")
