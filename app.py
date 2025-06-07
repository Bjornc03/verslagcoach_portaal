import streamlit as st
import openai
import docx

# Haal de OpenAI API key uit Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("Verslagcoach – Uploadportaal")
st.write("Upload hier je verslag (.docx) en ontvang automatisch AI-feedback!")

email = st.text_input("Vul je e-mailadres in:")
type_check = st.selectbox(
    "Hoeveel woorden heeft je verslag?",
    [
        "Minder dan 5.000 woorden",
        "Tussen 5.000 en 10.000 woorden",
        "Meer dan 10.000 woorden"
    ]
)
file = st.file_uploader("Upload je verslag (.docx)", type=["docx"])

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

if st.button("Verzenden"):
    if not email or not file:
        st.error("Vul je e-mail in en upload een bestand!")
    else:
        with st.spinner("Verslag wordt verwerkt door GPT-4o..."):
            verslag_tekst = extract_text_from_docx(file)
            if not verslag_tekst.strip():
                st.error("Het bestand lijkt leeg of niet leesbaar. Probeer een ander document.")
            else:
                prompt = f"Geef constructieve, vriendelijke en beknopte feedback op het volgende verslag. Geef tips voor verbetering en verwijs waar mogelijk naar relevante onderdelen:\n\n{verslag_tekst[:4000]}"
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    feedback = response.choices[0].message.content
                    st.success("Feedback van de AI:")
                    st.write(feedback)
                except Exception as e:
                    st.error(f"Er ging iets mis met de AI-feedback: {e}")


