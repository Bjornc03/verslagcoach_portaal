import streamlit as st
import openai
import docx
import pdfplumber
from fpdf import FPDF
import tempfile
import os

# 1. OpenAI API-key ophalen
openai.api_key = st.secrets["OPENAI_API_KEY"]

# 2. Prompt (let op: deze is NL en gestructureerd)
def maak_prompt(tekst):
    return f"""
Je bent een ervaren redacteur gespecialiseerd in het verbeteren van Nederlandstalige academische teksten op HBO-niveau.

Je krijgt een tekst met de opdracht om deze:
1. Te corrigeren op grammatica en spelling
2. Te herschrijven waar nodig voor betere zinsstructuur en stijl
3. De structuur per alinea logischer en duidelijker te maken

📌 Houd je aan de volgende instructies:
- ✍️ Schrijf in helder, zakelijk en toegankelijk Nederlands (HBO-stijl, dus niet te formeel of wollig)
- ❌ Verander niets aan de inhoud of betekenis
- 🛑 Maak geen onnodige herschrijvingen
- ✅ Geef per alinea concreet aan wat je hebt aangepast en waarom

📄 Structuur van jouw output per alinea:

**Alinea X:**
1. 💬 **Verbeterde tekst**:  
    [Nieuwe versie van de alinea]
2. 📝 **Toelichting per wijziging**:  
    - [Oude zin] → [Nieuwe zin] — reden: [korte uitleg]
    - ...

(Voeg bij twijfel ook 1 alternatieve formulering toe)

Als de tekst in het Engels is, geef dan Engelse feedback.

Hier is de tekst die je moet verbeteren:

\"\"\" 
{tekst}
\"\"\"
    """

# 3. Functies om tekst uit bestanden te halen
def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n\n"
    return text

# 4. PDF-generator
def maak_feedback_pdf(feedback):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for line in feedback.split("\n"):
        pdf.multi_cell(0, 10, line)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(temp.name)
    return temp.name

# 5. Streamlit interface
st.title("Verslagcoach – Uploadportaal (AI-feedback)")
st.write("Upload je verslag (.docx of .pdf). Je ontvangt direct AI-feedback als downloadbare PDF.")

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
            # Tekst uit bestand halen
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
                # Prompt samenstellen en AI aanroepen
                prompt = maak_prompt(verslag_tekst[:12000])  # tot 12.000 tekens (limiet)
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                    )
                    feedback = response.choices[0].message.content

                    # PDF genereren
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

                    # (Eventueel: toon ook kort samenvatting op scherm)
                    st.markdown("**Samenvatting van de feedback:**")
                    st.write(feedback[:1000] + ("..." if len(feedback) > 1000 else ""))

                except Exception as e:
                    st.error(f"Er ging iets mis met de AI-feedback: {e}")

