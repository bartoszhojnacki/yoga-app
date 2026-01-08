import streamlit as st
import pandas as pd
import random
from datetime import datetime
import os

# --- DEBUGGING ---
# st.write("📂 Obecny katalog roboczy:", os.getcwd())
# st.write("📄 Pliki w tym katalogu:", os.listdir())

# # Sprawdźmy czy plik istnieje z perspektywy Pythona
# if os.path.exists("yoga_library.csv"):
#     st.success("✅ Plik yoga_library.csv ISTNIEJE!")
# else:
#     st.error("❌ Plik yoga_library.csv NIE ISTNIEJE fizycznie w tym folderze.")


# 1. Konfiguracja strony
st.set_page_config(page_title="Joga App", page_icon="🧘‍♀️", layout="centered")

# 2. CSS - Stylizacja "Mobile First"
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {
                padding-top: 1rem;
                padding-bottom: 3rem;
            }
            /* Styl tagów */
            .tag-selected {
                background-color: #FF4B4B;
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.8rem;
                margin-right: 5px;
                display: inline-block;
                margin-bottom: 4px;
            }
            .tag-normal {
                background-color: #f0f2f6;
                color: #31333F;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.8rem;
                margin-right: 5px;
                display: inline-block;
                margin-bottom: 4px;
            }
            /* Styl dla przycisku losowania */
            .stButton button {
                border-radius: 12px;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 3. Ładowanie danych
# @st.cache_data
# 3. Ładowanie danych
# UWAGA: Usunąłem @st.cache_data tymczasowo, żeby wymusić odczyt pliku przy każdym odświeżeniu!
# Jak naprawimy błąd, możesz przywrócić dekorator.
# W pliku app.py

def load_data():
    csv_path = "yoga_library.csv"
    
    if not os.path.exists(csv_path):
        st.error(f"❌ Funkcja load_data nie widzi pliku: {csv_path}")
        return pd.DataFrame()

    try:
        # ZMIANA TUTAJ: on_bad_lines='skip' ignoruje uszkodzone wiersze
        df = pd.read_csv(csv_path, on_bad_lines='skip', engine='python')
        
        df.columns = df.columns.str.strip()
        
        df['tags_list'] = df['category'].fillna('').apply(
            lambda x: [tag.strip() for tag in str(x).split(',') if tag.strip()]
        )
        
        if 'intensity' not in df.columns: df['intensity'] = 1
        else: df['intensity'] = pd.to_numeric(df['intensity'], errors='coerce').fillna(1).astype(int)
            
        if 'props' not in df.columns: df['props'] = 'Brak'
        else: df['props'] = df['props'].fillna('Brak')
            
        return df
        
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd w load_data: {e}")
        return pd.DataFrame()
df = load_data()

# --- FUNKCJA POMOCNICZA: Rysowanie kropek intensywności ---
def render_intensity_html(level):
    try:
        lvl = int(level)
        lvl = max(1, min(lvl, 5))
    except:
        lvl = 1
        
    color = "#555" 
    if lvl >= 4: color = "#D32F2F"
    
    filled = "● " * lvl
    empty = "○ " * (5 - lvl)
    return f"<span style='color: {color}; letter-spacing: 1px;'>{filled}{empty}</span>"

# --- FUNKCJA: SUGEROWANIE DNIA (Toast) ---
day_of_week = datetime.now().weekday()
days_map = {
    0: ("Poniedziałek", "To dobry dzień na energię! Filtruj po 'Flow' lub 'Poranek'."),
    4: ("Piątek", "Koniec tygodnia! Czas na 'Relaks' lub 'Kręgosłup'."),
    5: ("Sobota", "Masz więcej czasu? Spróbuj czegoś dłuższego."),
    6: ("Niedziela", "Zregeneruj się przed nowym tygodniem.")
}
day_name, msg = days_map.get(day_of_week, ("Witaj na macie", "Jaka praktyka dzisiaj?"))
st.toast(f"📅 {day_name}! {msg}", icon="🧘")


# 4. Nagłówek
if df.empty:
    st.error("Brak bazy danych 'yoga_library.csv'. Uruchom najpierw generator i curatora!")
    st.stop()

st.title("🧘‍♀️ Studio Jogi")

# Pobranie dostępnych tagów i kanałów
all_available_tags = sorted(list(set([tag for sublist in df['tags_list'] for tag in sublist])))
all_channels = sorted(df['channel'].unique())

# 5. Panel Filtrów
with st.expander("🔍 Filtruj praktykę", expanded=True):
    
    # A. Tagi
    selected_tags = st.multiselect(
        "Cel:", 
        options=all_available_tags,
        placeholder="np. Poranek, Kręgosłup..."
    )
    
    # B. NOWOŚĆ: Kanał
    selected_channels = st.multiselect(
        "Kanał:",
        options=all_channels,
        placeholder="Wszyscy instruktorzy"
    )
    
    st.markdown("---")
    
    # C. Czas (Pills)
    TIME_RANGES = {
        "Wszystkie": (0, 999),
        "⚡ Do 6 min": (0, 6),
        "☕ 6 - 10 min": (6, 10),
        "🧘 10 - 20 min": (10, 20),
        "🔥 20 - 30 min": (20, 30),
        "💪 30 - 45 min": (30, 45),
        "🛌 45+ min": (45, 999)
    }
    
    time_choice = st.pills(
        "Czas:",
        options=list(TIME_RANGES.keys()),
        default="Wszystkie",
        selection_mode="single"
    )
    min_time, max_time = TIME_RANGES.get(time_choice, (0, 999))
    
    st.markdown("---")
    
    # D. Intensywność (Slider)
    intensity_range = st.slider("Poziom trudności (1-5):", 1, 5, (1, 5))

# 6. Logika Rankingu i Filtrowania
# Krok 1: Filtry "sztywne" (Czas, Intensywność)
filtered_df = df[
    (df['duration'] >= min_time) & 
    (df['duration'] <= max_time) &
    (df['intensity'] >= intensity_range[0]) &
    (df['intensity'] <= intensity_range[1])
].copy()

# Krok 2: Filtr kanału (jeśli wybrano)
if selected_channels:
    filtered_df = filtered_df[filtered_df['channel'].isin(selected_channels)]

# Krok 3: Ranking po tagach (Scoring)
if selected_tags:
    filtered_df['match_score'] = filtered_df['tags_list'].apply(
        lambda tags: len(set(tags).intersection(set(selected_tags)))
    )
    filtered_df = filtered_df[filtered_df['match_score'] > 0]
    filtered_df = filtered_df.sort_values(by=['match_score', 'duration'], ascending=[False, True])
else:
    filtered_df['match_score'] = 0
    filtered_df = filtered_df.sort_values(by=['duration'])


# --- FUNKCJA: WYLOSUJ COŚ ---
if not filtered_df.empty:
    st.markdown("###")
    if st.button("🎲 Nie wiem co wybrać (Losuj)", type="primary", use_container_width=True):
        random_practice = filtered_df.sample(1).iloc[0]
        
        st.success("✨ Los ślepy wybrał dla Ciebie:")
        
        with st.container(border=True):
            st.subheader(random_practice['title'])
            
            intens_html = render_intensity_html(random_practice['intensity'])
            props_txt = ""
            if random_practice['props'] and random_practice['props'] != "Brak":
                props_txt = f"&nbsp;|&nbsp; 🧱 {random_practice['props']}"
                
            st.markdown(f"Trudność: {intens_html} {props_txt}", unsafe_allow_html=True)
            st.caption(f"📺 {random_practice['channel']} | ⏱️ {random_practice['duration']} min")
            
            st.write(random_practice['description'])
            st.link_button("▶️ Uruchom wylosowaną", random_practice['url'], type="primary", use_container_width=True)
        
        if st.button("🔄 Wróć do listy"):
            st.rerun()
            
        st.stop()


# 7. Wyświetlanie Wyników (Lista)
st.caption(f"Znaleziono: {len(filtered_df)}")

if filtered_df.empty:
    st.info("Brak wyników. Zmień kryteria.")
else:
    for index, row in filtered_df.iterrows():
        try:
            with st.container():
                st.markdown("---") 
                
                # Tytuł
                st.subheader(row['title'])
                
                # Tagi
                tags_html = ""
                for tag in row['tags_list']:
                    style = 'tag-selected' if tag in selected_tags else 'tag-normal'
                    tags_html += f"<span class='{style}'>{tag}</span>"
                st.markdown(tags_html, unsafe_allow_html=True)
                
                # Info + Intensywność + Sprzęt
                intensity_visual = render_intensity_html(row['intensity'])
                
                props_info = ""
                if row['props'] and row['props'] != "Brak":
                    props_info = f"&nbsp; | &nbsp; 🧱 {row['props']}"
                
                st.markdown(
                    f"""
                    <div style="margin-top: 5px; margin-bottom: 5px; font-size: 0.9em; color: #555;">
                        Trudność: <b>{intensity_visual}</b> {props_info} <br>
                        <span style="color: grey; font-size: 0.9em">📺 {row['channel']} &nbsp;|&nbsp; ⏱️ {row['duration']} min</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Opis
                desc = str(row['description'])
                if desc.lower() == 'nan' or not desc:
                    desc = "Brak opisu."
                    
                if len(desc) > 200:
                    st.write(desc[:200] + "...")
                    with st.expander("Rozwiń opis"):
                        st.write(desc)
                else:
                    st.write(desc)
                
                # Przycisk
                st.link_button("▶️ Start", row['url'], use_container_width=True)
                
        except Exception as e:
            st.error(f"Błąd wiersza: {e}")