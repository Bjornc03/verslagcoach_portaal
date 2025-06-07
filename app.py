import streamlit as st

st.title("Verslagcoach – Uploadportaal")
st.write("Upload hier je verslag en ontvang persoonlijke feedback per mail!")

# E-mailadres invullen
email = st.text_input("Vul je e-mailadres in:")

# Keuze op basis van aantal woorden
type_check = st.selectbox(
    "Hoeveel woorden heeft je verslag?",
    [
        "Minder dan 5.000 woorden",
        "Tussen 5.000 en 10.000 woorden",
        "Meer dan 10.000 woorden"
    ]
)

# Bestand uploaden
file = st.file_uploader("Upload je verslag (.docx of .pdf)", type=["docx", "pdf"])

# Verstuur-knop
if st.button("Verzenden"):
    if not email or not file:
        st.error("Vul je e-mail in en upload een bestand!")
    else:
        st.success("Je verslag is ontvangen! Je krijgt per mail bericht zodra het verwerkt is.")
        # Hier kun je later je eigen verwerking (AI, mail, etc.) toevoegen

