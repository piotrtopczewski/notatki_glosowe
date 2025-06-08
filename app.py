from io import BytesIO
import streamlit as st
from audiorecorder import audiorecorder  # Poprawiony import
from dotenv import dotenv_values
from hashlib import md5
from openai import OpenAI
from streamlit_javascript import st_javascript

env = dotenv_values(".env")

AUDIO_TRANSCRIBE_MODEL = "whisper-1"

def get_openai_client():
    return OpenAI(api_key=st.session_state["openai_api_key"])

def transcribe_audio(audio_bytes):
    openai_client = get_openai_client()
    audio_file = BytesIO(audio_bytes)
    audio_file.name = "audio.mp3"
    transcript = openai_client.audio.transcriptions.create(
        file=audio_file,
        model=AUDIO_TRANSCRIBE_MODEL,
        response_format="verbose_json",
        language="pl"
    )

    return transcript.text


#
# MAIN
#
st.set_page_config(page_title="Audio Notatki", layout="centered")

# Inicjalizacja stanu logowania
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "do_clear_password" not in st.session_state:
    st.session_state["do_clear_password"] = False

# Panel logowania w sidebar
with st.sidebar:
    st.title("Logowanie")
    
    # Obsługa flagi czyszczenia hasła
    if st.session_state.get("do_clear_password"):
        st.session_state["do_clear_password"] = False
        password_value = ""
    else:
        password_value = st.session_state.get("password_input", "")
    
    password_input = st.text_input("Podaj hasło", type="password", key="password_input", value=password_value)

    if st.button("Zaloguj", key="login_button"):
        # Check if the password is correct
        if password_input == env.get("PASSWORD"):
            st.session_state["logged_in"] = True
            st.success("Zalogowano pomyślnie!")
            st.rerun()  # Odśwież stronę po zalogowaniu
        else:
            st.error("Nieprawidłowe hasło. Spróbuj ponownie.")
            st.session_state["logged_in"] = False

    # Przycisk wylogowania (widoczny tylko gdy użytkownik jest zalogowany)
    if st.session_state["logged_in"]:
        if st.button("Wyloguj"):
            st.session_state["logged_in"] = False
            st.session_state["do_clear_password"] = True
            st.rerun()

# Sprawdź, czy użytkownik jest zalogowany
if not st.session_state["logged_in"]:
    st.title("Audio Notatki")
    st.warning("Musisz się zalogować, aby korzystać z aplikacji.")
    st.stop()  # Zatrzymaj wykonywanie kodu, jeśli użytkownik nie jest zalogowany

# OpenAI API key protection
if not st.session_state.get("openai_api_key"):
    if "OPENAI_API_KEY" in env:
        st.session_state["openai_api_key"] = env["OPENAI_API_KEY"]
    else:
        st.info("Dodaj swój klucz API OpenAI aby móc korzystać z tej aplikacji")
        st.session_state["openai_api_key"] = st.text_input("Klucz API", type="password")
        if st.session_state["openai_api_key"]:
            st.rerun()

if not st.session_state.get("openai_api_key"):
    st.stop()

# Session state initialization
if "note_audio_bytes_md5" not in st.session_state:
    st.session_state["note_audio_bytes_md5"] = None

if "note_audio_bytes" not in st.session_state:
    st.session_state["note_audio_bytes"] = None

if "note_audio_text" not in st.session_state:
    st.session_state["note_audio_text"] = ""

# Główny interfejs aplikacji (widoczny tylko dla zalogowanych użytkowników)
st.title("Audio Notatki")
note_audio = audiorecorder(
    start_prompt="Nagraj notatkę",
    stop_prompt="Zatrzymaj nagrywanie",
)
if note_audio:
    audio = BytesIO()
    note_audio.export(audio, format="mp3")
    st.session_state["note_audio_bytes"] = audio.getvalue()

    current_md5 = md5(st.session_state["note_audio_bytes"]).hexdigest()
    if st.session_state["note_audio_bytes_md5"] != current_md5:
        st.session_state["note_audio_text"] = ""
        st.session_state["note_audio_bytes_md5"] = current_md5

    st.audio(st.session_state["note_audio_bytes"], format="audio/mp3")

    if st.button("Transkrybuj audio"):
        st.session_state["note_audio_text"] = transcribe_audio(st.session_state["note_audio_bytes"])

    if st.session_state["note_audio_text"]:
        edited_text = st.text_area("Edytuj notatkę", value=st.session_state["note_audio_text"])
        
        # Dodanie przycisku do pobrania transkrypcji jako plik tekstowy
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="Pobierz jako plik",
                data=edited_text,
                file_name="transkrypcja.txt",
                mime="text/plain",
            )
        
        with col2:
            if st.button("Kopiuj do schowka", key=f"copy_btn_{st.session_state['note_audio_bytes_md5']}_{hash(edited_text)}"):
                # Pobierz tekst bezpośrednio ze stanu sesji
                text_to_copy = st.session_state["note_audio_text"]
                
                # Bezpieczne escapowanie tekstu
                import json
                escaped_text = json.dumps(text_to_copy)
                
                # Użyj nowej metody kopiowania do schowka (bardziej niezawodna)
                js_code = f"""
                navigator.clipboard.writeText({escaped_text})
                .then(() => {{
                    return true;
                }})
                .catch(err => {{
                    console.error('Nie można skopiować tekstu: ', err);
                    return false;
                }});
                """
                
                success = st_javascript(js_code)
                
                if success:
                    st.success("Transkrypcja została skopiowana do schowka systemowego!")
                else:
                    # Zapasowa metoda, jeśli nowoczesne API nie zadziała
                    backup_js = f"""
                    try {{
                        const el = document.createElement('textarea');
                        el.value = {escaped_text};
                        el.setAttribute('readonly', '');
                        el.style.position = 'absolute';
                        el.style.left = '-9999px';
                        document.body.appendChild(el);
                        el.select();
                        document.execCommand('copy');
                        document.body.removeChild(el);
                        return true;
                    }} catch (err) {{
                        console.error('Błąd kopiowania: ', err);
                        return false;
                    }}
                    """
                    backup_success = st_javascript(backup_js)
                    
                    if backup_success:
                        st.success("Transkrypcja została skopiowana do schowka systemowego!")
                    else:
                        st.error("Nie udało się skopiować tekstu do schowka. Spróbuj użyć przycisku 'Pobierz jako plik'.")
