import streamlit as st
import openai
import docx
import pdfplumber
import tempfile
import os

# ======= OpenAI API-key uit Streamlit secrets =========
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ======= Krachtige prompt met samenvatting & rode draad + alleen fouten =======
def maak_prompt(tekst):
    return f"""
Je bent een ervaren taalkundige en redacteur. Analyseer de onderstaande tekst op de volgende manier:

1. Geef een korte samenvatting van de inhoud (maximaal 300 woorden).
2. Geef een beoordeling van de rode draad en logische opbouw (maximaal 200 woorden).
3. Geef daarna **uitsluitend** per alinea de zinnen die grammaticaal of taalkundig onjuist zijn.
   - Voor elke fout:
     1. De originele zin
     2. De verbeterde versie
     3. Een korte uitleg (maximaal 1 zin) waarom het fout is

Vermeld geen alinea’s waar geen fouten in staan.  
Schrijf alleen in het Nederlands (of in het Engels als de input Engels is).

**Structuur van de feedback:**

# Samenvatting

# Rode draad & structuur

# Fouten per alinea

Alinea X:
- Originele zin: ...
- Verbeterde zin: ...
- Uitleg: ...

(herhaal dit voor alle foute zinnen in deze alinea)

Hier is de tekst:
\"\"\"
{tekst}
\"\"\"
"""

# ======= Tekst extractie-functies =======
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

# ======= Word-generator voor feedback =======
def maak_feedback_docx(feedback):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc = docx.Document()
    doc.add_heading("AI Feedback – Samenvatting & Taalcontrole", 0)
    section = None
    for line in feedback.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("# samenvatting"):
            section = "Samenvatting"
            doc.add_heading("Samenvatting", level=1)
        elif line.lower().startswith("# rode draad"):
            section = "Rode draad & structuur"
            doc.add_heading("Rode draad & structuur", level=1)
        elif line.lower().startswith("# fouten per alinea"):
            section = "Fouten"
            doc.add_heading("Fouten per alinea", level=1)
        elif line.lower().startswith("alinea"):
            doc.add_heading(line, level=2)
        elif line.startswith("- Originele zin:"):
            doc.add_paragraph(line, style="List Bullet")
        elif line.startswith("- Verbeterde zin:"):
            doc.add_paragraph(line, style="List Bullet")
        elif line.startswith("- Uitleg:"):
            doc.add_paragraph(line, style="List Bullet")
        elif section:
            doc.add_paragraph(line)
    doc.save(temp.name)
    return temp.name

# ======= Streamlit interface =======
st.title("Verslagcoach – Samenvatting & Taalcontrole")
st.write("Upload je verslag (.docx of .pdf). Je ontvangt AI-feedback als Word-bestand: eerst een samenvatting en rode draad, daarna alleen zinnen met fouten per alinea.")

email = st.text_input("Vul je e-mailadres in (optioneel):")
type_check = st.selectbox(
    "Hoeveel woorden heeft je verslag?",
    [
        "Minder dan 5.000 woorden",
        "Tussen 5.000 en 10.000 woorden",
        "Meer dan 10.000 woorden"
    ]
)
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
                prompt = maak_prompt(verslag_tekst[:8000])
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                    )
                    feedback = response.choices[0].message.content

                    docx_path = maak_feedback_docx(feedback)
                    with open(docx_path, "rb") as f:
                        st.success("Download hieronder je persoonlijke AI-feedback als Word-bestand:")
                        st.download_button(
                            label="Download feedback (.docx)",
                            data=f.read(),
                            file_name="AI-feedback-samenvatting-taalcontrole.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    os.remove(docx_path)

                    st.markdown("**Korte impressie van de feedback:**")
                    st.write(feedback[:1000] + ("..." if len(feedback) > 1000 else ""))

                except Exception as e:
                    st.error(f"Er ging iets mis met de AI-feedback: {e}")
