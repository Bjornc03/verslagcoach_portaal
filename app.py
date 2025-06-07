import streamlit as st
import openai
import docx
import pdfplumber
import tempfile
import os
import math

# ======= OpenAI API-key uit Streamlit secrets =========
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ======= Prompt met beoordeling, rode draad, alleen fouten per deel =======
def maak_prompt(tekst, deel_nummer=None):
    deelinfo = f"Dit is deel {deel_nummer} van het verslag.\n" if deel_nummer else ""
    return f"""
{deelinfo}
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

Structuur van de feedback:

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

# ======= Functie om tekst automatisch te splitsen op ~2000 woorden per deel =======
def split_text_into_chunks(text, max_words=2000):
    words = text.split()
    num_chunks = math.ceil(len(words) / max_words)
    chunks = []
    for i in range(num_chunks):
        chunk_words = words[i*max_words : (i+1)*max_words]
        chunks.append(" ".join(chunk_words))
    return chunks

# ======= Word-generator voor gecombineerde feedback =======
def maak_feedback_docx(all_feedback):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc = docx.Document()
    doc.add_heading("AI Feedback – Samenvatting & Taalcontrole", 0)
    for i, feedback in enumerate(all_feedback, start=1):
        if len(all_feedback) > 1:
            doc.add_heading(f"Deel {i}", level=1)
        section = None
        for line in feedback.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("# samenvatting"):
                section = "Samenvatting"
                doc.add_heading("Samenvatting", level=2)
            elif line.lower().startswith("# rode draad"):
                section = "Rode draad & structuur"
                doc.add_heading("Rode draad & structuur", level=2)
            elif line.lower().startswith("# fouten per alinea"):
                section = "Fouten"
                doc.add_heading("Fouten per alinea", level=2)
            elif line.lower().startswith("alinea"):
                doc.add_heading(line, level=3)
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
st.title("Verslagcoach – AI-feedback voor grote documenten")
st.write("Upload je verslag (.docx of .pdf). Jouw document wordt automatisch in delen gesplitst, elk deel krijgt grondige AI-feedback (samenvatting, rode draad, alleen taalfouten), en alles wordt samengevoegd tot één Word-bestand.")

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
                # Automatisch splitsen op delen van ca. 2000 woorden
                chunks = split_text_into_chunks(verslag_tekst, max_words=2000)
                all_feedback = []
                for i, chunk in enumerate(chunks, start=1):
                    st.info(f"AI verwerkt deel {i} van {len(chunks)}...")
                    prompt = maak_prompt(chunk, deel_nummer=i if len(chunks) > 1 else None)
                    try:
                        response = openai.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2,
                        )
                        feedback = response.choices[0].message.content
                        all_feedback.append(feedback)
                    except Exception as e:
                        st.error(f"Fout bij AI-verwerking van deel {i}: {e}")
                        all_feedback.append(f"[AI-verwerking mislukt voor deel {i}]")

                docx_path = maak_feedback_docx(all_feedback)
                with open(docx_path, "rb") as f:
                    st.success("Download hieronder je complete AI-feedback als Word-bestand:")
                    st.download_button(
                        label="Download feedback (.docx)",
                        data=f.read(),
                        file_name="AI-feedback-volledig.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                os.remove(docx_path)

                # Optioneel: korte impressie van feedback eerste deel
                st.markdown("**Korte impressie van de feedback:**")
                st.write(all_feedback[0][:1000] + ("..." if len(all_feedback[0]) > 1000 else ""))
