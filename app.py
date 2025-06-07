import streamlit as st
import openai
import docx
import pdfplumber
from fpdf import FPDF
import tempfile
import os

# ======= Functie om niet-latin1-tekens te filteren ========
def make_latin1(text):
    return text.encode('latin-1', 'ignore').decode('latin-1')

# ======= OpenAI API-key uit Streamlit secrets =========
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ======= NIEUWE krachtige promptfunctie =========
def maak_prompt(tekst):
    return f"""
Je bent een ervaren redacteur. Analyseer de onderstaande tekst volgens deze structuur:

1. Samenvatting (max 300 woorden)
2. Rode draad & structuur (logische opbouw, samenhang inleiding, kern, conclusie)
3. Taalgebruik, spelling en grammatica
4. Bronvermelding en literatuurlijst (benoem expliciet of deze aanwezig en correct is)
5. Tips voor verbetering

Let op:
- Is de tekst langer dan 1500 woorden, SPLITS de tekst dan automatisch in logische delen (bijvoorbeeld per hoofdstuk, of maximaal per 1000 woorden per blok). Geef voor elk deel dezelfde feedback (1-5) en, als het kan, een korte per-alinea analyse. Plaats de feedback van alle delen onder elkaar, met duidelijke koppen als "Deel 1", "Deel 2", enzovoort.
- Geef geen per-alinea feedback als er meer dan 20 alinea’s per blok zijn; vat dan de belangrijkste punten samen.
- Behandel alle gevraagde onderdelen. Sla geen enkele sectie over.
- Schrijf in helder, zakelijk en begrijpelijk Nederlands (of in het Engels als de input Engels is).
- Gebruik duidelijke headings (met # voor kopjes), witregels tussen de onderdelen en bullets (-) waar nuttig.

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

# ======= Markdown-achtige PDF-generator =======
class FeedbackPDF(FPDF):
    def header(self):
        pass

    def chapter_title(self, txt, level=1):
        if level == 1:
            self.set_font('Arial', 'B', 16)
            self.cell(0, 12, txt, ln=True)
        elif level == 2:
            self.set_font('Arial', 'B', 13)
            self.cell(0, 10, txt, ln=True)
        self.ln(2)

    def bullet(self, txt):
        self.set_font('Arial', '', 12)
        self.cell(10)
        self.cell(0, 10, f'- {txt}', ln=True)

    def paragraph(self, txt):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 8, txt)
        self.ln(1)

def maak_feedback_pdf(feedback):
    pdf = FeedbackPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    feedback = make_latin1(feedback)
    for line in feedback.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        if line.startswith("### "):
            pdf.chapter_title(line.replace("### ", ""), level=2)
        elif line.startswith("## "):
            pdf.chapter_title(line.replace("## ", ""), level=2)
        elif line.startswith("# "):
            pdf.chapter_title(line.replace("# ", ""), level=1)
        elif line.startswith("- "):
            pdf.bullet(line[2:])
        else:
            pdf.paragraph(line)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(temp.name)
    return temp.name

# ======= Streamlit interface =======
st.title("Verslagcoach – Uploadportaal (AI-feedback)")
st.write("Upload je verslag (.docx of .pdf). Je ontvangt direct AI-feedback als overzichtelijke PDF met duidelijke kopjes.")

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
        with st.spinner("Verslag verwerken en AI-feedback genereren..."):
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
                prompt = maak_prompt(verslag_tekst[:12000])  # Pas evt. limiet aan
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                    )
                    feedback = response.choices[0].message.content
                    feedback = make_latin1(feedback)

                    pdf_path = maak_feedback_pdf(feedback)
                    with open(pdf_path, "rb") as f:
                        st.success("Download hieronder je persoonlijke AI-feedback als PDF:")
                        st.download_button(
                            label="Download feedback (PDF)",
                            data=f.read(),
                            file_name="AI-feedback-verslag.pdf",
                            mime="application/pdf"
                        )
                    os.remove(pdf_path)

                    st.markdown("**Samenvatting van de feedback:**")
                    st.write(feedback[:1000] + ("..." if len(feedback) > 1000 else ""))

                except Exception as e:
                    st.error(f"Er ging iets mis met de AI-feedback: {e}")
