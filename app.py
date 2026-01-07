import streamlit as st
import pandas as pd

# 1. Konfiguracja strony
st.set_page_config(page_title="Joga App", page_icon="🧘‍♀️", layout="centered")

# 2. CSS - Stylizacja
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {
                padding-top: 1rem;
                padding-bottom: 3rem;
            }
            .tag-selected {
                background-color: #FF4B4B;
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.8rem;
                margin-right: 5px;
                display: inline-block;
            }
            .tag-normal {
                background-color: #f0f2f6;
                color: #31333F;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.8rem;
                margin-right: 5px;
                display: inline-block;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 3. Ładowanie danych
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("yoga_library.csv")
        df.columns = df.columns.str.strip() # Usuwamy spacje z nagłówków
        
        # Parsowanie tagów
        df['tags_list'] = df['category'].fillna('').apply(
            lambda x: [tag.strip() for tag in str(x).split(',') if tag.strip()]
        )
        return df
    except Exception as e:
        st.error(f"Błąd ładowania pliku CSV: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Brak danych. Sprawdź plik yoga_data.csv")
    st.stop()

# Pobranie dostępnych tagów
all_available_tags = sorted(list(set([tag for sublist in df['tags_list'] for tag in sublist])))

# 4. Nagłówek
st.title("🧘‍♀️ Studio Jogi")

# 5. Panel Filtrów
with st.expander("🔍 Filtruj praktykę", expanded=True):
    
    # A. Wybór tagów
    selected_tags = st.multiselect(
        "Na czym Ci zależy?", 
        options=all_available_tags,
        placeholder="np. Poranek, Kręgosłup..."
    )
    
    st.markdown("---") # Oddzielenie sekcji
    
    # B. Wybór czasu (Nowa logika: Przedziały)
    # Definiujemy słownik: "Etykieta": (min_minut, max_minut)
    TIME_RANGES = {
        "Wszystkie": (0, 999),
        "⚡ Do 6 min": (0, 6),
        "☕ 6 - 10 min": (6, 10),
        "🧘 10 - 20 min": (10, 20),
        "🔥 20 - 30 min": (20, 30),
        "💪 30 - 45 min": (30, 45),
        "🛌 45+ min": (45, 999)
    }
    
    # Wyświetlamy pills (pastylki)
    time_choice = st.pills(
        "Ile masz czasu?",
        options=list(TIME_RANGES.keys()),
        default="Wszystkie",
        selection_mode="single"
    )
    
    # Pobieramy zakres liczbowy na podstawie wyboru (zabezpieczenie na wypadek braku wyboru)
    selected_range = TIME_RANGES.get(time_choice, (0, 999))
    min_time, max_time = selected_range

# 6. Logika Rankingu i Filtrowania
# Krok A: Filtr czasu
filtered_df = df[
    (df['duration'] >= min_time) & 
    (df['duration'] <= max_time)
].copy()

# Krok B: Ranking po tagach
if selected_tags:
    filtered_df['match_score'] = filtered_df['tags_list'].apply(
        lambda tags: len(set(tags).intersection(set(selected_tags)))
    )
    # Pokaż tylko te, które mają przynajmniej 1 wspólny tag
    filtered_df = filtered_df[filtered_df['match_score'] > 0]
    # Sortuj: Najpierw trafność, potem czas
    filtered_df = filtered_df.sort_values(by=['match_score', 'duration'], ascending=[False, True])
else:
    # Jeśli brak tagów, sortuj po czasie
    filtered_df['match_score'] = 0
    filtered_df = filtered_df.sort_values(by=['duration'])

# 7. Wyświetlanie Wyników
st.caption(f"Znaleziono: {len(filtered_df)}")

if filtered_df.empty:
    st.info("Brak wyników w tym przedziale czasowym dla wybranych kategorii.")
else:
    for index, row in filtered_df.iterrows():
        try:
            with st.container():
                st.markdown("---") 
                
                # Tytuł
                st.subheader(row['title'])
                
                # Renderowanie kolorowych tagów
                tags_html = ""
                for tag in row['tags_list']:
                    if tag in selected_tags:
                        tags_html += f"<span class='tag-selected'>{tag}</span>"
                    else:
                        tags_html += f"<span class='tag-normal'>{tag}</span>"
                st.markdown(tags_html, unsafe_allow_html=True)
                
                # Informacje techniczne
                st.caption(f"📺 {row['channel']} | ⏱️ {row['duration']} min")
                
                # Opis (skrócony)
                desc = str(row['description'])
                if len(desc) > 200:
                    st.write(desc[:200] + "...")
                    with st.expander("Rozwiń opis"):
                        st.write(desc)
                else:
                    st.write(desc)
                
                # Duży przycisk na dole
                st.link_button("▶️ Start", row['url'], type="primary", use_container_width=True)
                
        except Exception as e:
            st.error(f"Błąd wiersza: {e}")