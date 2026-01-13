import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
from datetime import datetime
import os
from pyairtable import Api

try:
    AT_API_KEY = st.secrets["AIRTABLE_API_KEY"]
    AT_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
    AT_TABLE_NAME = st.secrets["AIRTABLE_TABLE_NAME"]
    at_api = Api(AT_API_KEY)
    at_table = at_api.table(AT_BASE_ID, AT_TABLE_NAME)
except Exception:
    # Fallback, żeby aplikacja nie wybuchła bez kluczy
    at_table = None



if st.button("Testuj połączenie z bazą"):
    try:
        # 1. Sprawdzamy czy są sekrety
        st.write("Sprawdzam klucze...")
        k = st.secrets["AIRTABLE_API_KEY"]
        b = st.secrets["AIRTABLE_BASE_ID"]
        t = st.secrets["AIRTABLE_TABLE_NAME"]
        st.write(f"Baza: {b}, Tabela: {t}")
        
        # 2. Próba połączenia
        from pyairtable import Api
        api = Api(k)
        table = api.table(b, t)
        
        # 3. Próba zapisu
        st.write("Próbuję zapisać rekord testowy...")
        table.create({"Title": "TEST_POŁĄCZENIA", "Favorite": True, "Count": 1})
        
        st.success("✅ SUKCES! Rekord dodany. Sprawdź Airtable.")
    except Exception as e:
        st.error(f"❌ BŁĄD: {e}")
        st.info("Podpowiedź: Sprawdź uprawnienia tokena, ID bazy i nazwy kolumn.")




@st.cache_data(ttl=10)
def load_user_stats():
    if not at_table: return {"favorites": [], "usage_count": {}}
    
    try:
        records = at_table.all()
        favs = []
        counts = {}
        
        for r in records:
            fields = r.get('fields', {})
            rid = fields.get('Title')
            if not rid: continue
            
            # Zbieramy ulubione
            if fields.get('Favorite'):
                favs.append(rid)
            
            # Zbieramy liczniki
            cnt = fields.get('Count', 0)
            if cnt > 0:
                counts[rid] = cnt
                
        return {"favorites": favs, "usage_count": counts}
    except Exception as e:
        print(f"Airtable Error: {e}")
        return {"favorites": [], "usage_count": {}}
    
def get_airtable_record(title):
    """Znajduje rekord dla konkretnego pliku."""
    if not at_table: return None
    formula = f"{{Title}}='{title}'"
    matches = at_table.all(formula=formula)
    if matches:
        return matches[0]
    return None


def toggle_favorite(filename):
    if not at_table or not filename: return # Guard clause
    
    record = get_airtable_record(filename)
    if record:
        current = record['fields'].get('Favorite', False)
        at_table.update(record['id'], {'Favorite': not current})
    else:
        at_table.create({'Title': filename, 'Favorite': True, 'Count': 0})
    load_user_stats.clear()
    
def increment_usage_stats(title):
    if not at_table: return
    record = get_airtable_record(title)
    if record:
        current = record['fields'].get('Count', 0)
        at_table.update(record['id'], {'Count': current + 1})
    else:
        at_table.create({'Title': title, 'Favorite': False, 'Count': 1})
    load_user_stats.clear()


# 1. Konfiguracja strony
st.set_page_config(page_title="Joga & Mobility", page_icon="🧘‍♀️", layout="centered")

# 2. CSS - Stylizacja
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {padding-top: 1rem; padding-bottom: 3rem;}
            /* Styl tagów */
            .tag-selected {background-color: #FF4B4B; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem; margin-right: 5px; display: inline-block; margin-bottom: 4px;}
            .tag-normal {background-color: #f0f2f6; color: #31333F; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem; margin-right: 5px; display: inline-block; margin-bottom: 4px;}
            .stTabs [data-baseweb="tab-list"] {gap: 20px;}
            .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px;}
            .stTabs [aria-selected="true"] {background-color: #FF4B4B; color: white;}
            
            /* Styl dla tagów Mobility (niebieskie dla odmiany) */
            .mob-tag-type {background-color: #E3F2FD; color: #0D47A1; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; border: 1px solid #BBDEFB;}
            .mob-tag-body {background-color: #E8F5E9; color: #1B5E20; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; border: 1px solid #C8E6C9;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- DEFINICJA SŁÓW KLUCZOWYCH DLA MOBILITY ---
MOBILITY_KEYWORDS = {
    # Kategoria: [Lista słów, które jej szukają]
    "types": {
        "Stretching": ["rozciąganie", "stretching", "stretch", "elastyczność"],
        "Mobility": ["mobilność", "mobility", "zakresy", "ruchomość"],
        "Rolowanie": ["rolowanie", "roller", "rozluźnianie", "automasaż", "piłeczka"],
        "Wzmacnianie": ["wzmacnianie", "siła", "stabilizacja", "aktywacja"]
    },
    "body_parts": {
        "Biodra": ["biodra", "bioder", "miednica", "pośladki", "otwieranie bioder"],
        "Barki & Szyja": ["barki", "barków", "ramiona", "szyja", "kark", "klatka"],
        "Kręgosłup": ["kręgosłup", "plecy", "lędźwi", "grzbiet"],
        "Nogi": ["nogi", "nóg", "uda", "staw skokowy", "stopy", "łydki", "kolana"],
        "Nadgarstki": ["nadgarstki", "dłonie", "przedramiona"],
        "Całe ciało": ["całe ciało", "full body", "ogólne"]
    }
}

def auto_tag_mobility(row):
    """Funkcja analizuje tekst i zwraca znalezione tagi."""
    # Łączymy tytuł i opis, zamieniamy na małe litery
    text = (str(row['title']) + " " + str(row.get('description', ''))).lower()
    
    found_types = []
    found_body = []
    
    # Szukamy typu
    for cat, keywords in MOBILITY_KEYWORDS['types'].items():
        if any(k in text for k in keywords):
            found_types.append(cat)
            
    # Szukamy części ciała
    for cat, keywords in MOBILITY_KEYWORDS['body_parts'].items():
        if any(k in text for k in keywords):
            found_body.append(cat)
            
    return found_types, found_body

# 3. Ładowanie danych
def load_yoga_data():
    try:
        df = pd.read_csv("yoga_library.csv", on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        df['tags_list'] = df['category'].fillna('').apply(lambda x: [tag.strip() for tag in str(x).split(',') if tag.strip()])
        if 'intensity' not in df.columns: df['intensity'] = 1
        else: df['intensity'] = pd.to_numeric(df['intensity'], errors='coerce').fillna(1).astype(int)
        if 'props' not in df.columns: df['props'] = 'Brak'
        else: df['props'] = df['props'].fillna('Brak')
        return df
    except Exception:
        return pd.DataFrame()

def load_mobility_data():
    try:
        df = pd.read_csv("mobility.csv", on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        
        # --- AUTO-TAGOWANIE W LOCIE ---
        # Tworzymy dwie nowe kolumny z listami tagów
        tags_result = df.apply(auto_tag_mobility, axis=1)
        df['type_tags'] = tags_result.apply(lambda x: x[0])
        df['body_tags'] = tags_result.apply(lambda x: x[1])
        
        return df
    except Exception:
        return pd.DataFrame()

# Wczytanie
df_yoga = load_yoga_data()
df_mob = load_mobility_data()

# 4. Funkcje pomocnicze
def render_intensity_html(level):
    try: lvl = max(1, min(int(level), 5))
    except: lvl = 1
    color = "#D32F2F" if lvl >= 4 else "#555"
    return f"<span style='color: {color}; letter-spacing: 1px;'>{'● '*lvl}{'○ '*(5-lvl)}</span>"

# Sugestia dnia (Toast)
day_of_week = datetime.now().weekday()
days_map = {0: "Poniedziałek", 4: "Piątek", 5: "Sobota", 6: "Niedziela"}
day_name = days_map.get(day_of_week, "Dzień dobry")
st.toast(f"📅 {day_name}! Wybierz zakładkę poniżej.", icon="👋")

st.title("Studio Ruchu")

# --- ZAKŁADKI ---
tab_yoga, tab_mob = st.tabs(["🧘‍♀️ Joga", "🤸‍♂️ Mobility & Stretch"])
user_stats = load_user_stats()
# ==================================================
# ZAKŁADKA 1: JOGA
# ==================================================
with tab_yoga:
    if df_yoga.empty:
        st.info("Brak bazy jogi (yoga_library.csv).")
    else:
        all_tags = sorted(list(set([t for l in df_yoga['tags_list'] for t in l])))
        all_channels = sorted(df_yoga['channel'].unique())

        with st.expander("🔍 Filtry Jogi", expanded=True):
            y_tags = st.multiselect("Cel:", all_tags, key="y_tags")
            y_chan = st.multiselect("Kanał:", all_channels, key="y_chan")
            st.markdown("---")
            TIME_RANGES = {"Wszystkie": (0, 999), "⚡ Do 5 min": (0, 6),"⚡ Do 10 min": (6, 10),"⚡ Do 20 min": (10, 20), "🧘 20-30 min": (20, 30), "💪 30-45 min": (30, 45), "🛌 45+ min": (45, 999)}
            y_time_choice = st.pills("Czas:", list(TIME_RANGES.keys()), default="Wszystkie", key="y_time")
            y_min, y_max = TIME_RANGES.get(y_time_choice, (0, 999))
            st.markdown("---")
            y_intens = st.slider("Trudność:", 1, 5, (1, 5), key="y_int")

        df_y_filt = df_yoga[
            (df_yoga['duration'] >= y_min) & (df_yoga['duration'] <= y_max) &
            (df_yoga['intensity'] >= y_intens[0]) & (df_yoga['intensity'] <= y_intens[1])
        ].copy()
        
        if y_chan: df_y_filt = df_y_filt[df_y_filt['channel'].isin(y_chan)]
        if y_tags:
            df_y_filt['score'] = df_y_filt['tags_list'].apply(lambda x: len(set(x).intersection(set(y_tags))))
            df_y_filt = df_y_filt[df_y_filt['score'] > 0].sort_values(by=['score', 'duration'], ascending=[False, True])
        else:
            df_y_filt = df_y_filt.sort_values(by=['duration'])

        if not df_y_filt.empty:
             if st.button("🎲 Wylosuj Jogę", key="rnd_yoga", type="primary", use_container_width=True):
                r = df_y_filt.sample(1).iloc[0]
                st.success(f"Wylosowano: {r['title']}")
                st.link_button("▶️ Start", r['url'], use_container_width=True)

        st.caption(f"Wyników: {len(df_y_filt)}")
        for _, row in df_y_filt.iterrows():
            with st.container():
                st.markdown("---")
                st.subheader(row['title'])
                tags_html = "".join([f"<span class='tag-selected'>{t}</span>" if t in y_tags else f"<span class='tag-normal'>{t}</span>" for t in row['tags_list']])
                st.markdown(tags_html, unsafe_allow_html=True)
                intens_html = render_intensity_html(row['intensity'])
                props_info = f"&nbsp;| 🧱 {row['props']}" if row['props'] != "Brak" else ""
                st.markdown(f"<div style='color:#555; font-size:0.9em; margin:5px 0;'>Trudność: <b>{intens_html}</b>{props_info}<br>📺 {row['channel']} | ⏱️ {row['duration']} min</div>", unsafe_allow_html=True)
                desc = str(row['description'])
                if len(desc) > 200:
                    st.write(desc[:200] + "...")
                    with st.expander("Więcej"): st.write(desc)
                else:
                    st.write(desc)
                
                if row['title'] in user_stats['favorites']:
                    label = "Usuń z ulubionych"
                else:
                    label = "Dodaj do ulubionych"
                    
                st.button(
                    label=label,
                    key=f"fav_{row['title']}_{_}",
                    on_click=toggle_favorite,
                    args=(f"{row['title']}",)  # Tutaj przekazujemy tytuł
                )
                if st.button("▶️ Start", key=f"start_{row['title']}_{_}"):
                    increment_usage_stats(row['title'])
                    st.toast(f"Uruchamiam: {row['title']}")
                    
                    js_code = f"""
                    <script>
                    window.open("{row['url']}", "_blank");
                    </script>
                    """
                    components.html(js_code, height=0)
                # st.link_button("▶️ Start", row['url'], use_container_width=True)


# ==================================================
# ZAKŁADKA 2: MOBILITY & STRETCH
# ==================================================
with tab_mob:
    if df_mob.empty:
        st.info("Brak bazy mobility (mobility.csv).")
    else:
        m_channels = sorted(df_mob['channel'].unique())
        
        # Pobieramy wszystkie unikalne tagi, które udało się wykryć
        all_types = sorted(list(MOBILITY_KEYWORDS['types'].keys()))
        all_body = sorted(list(MOBILITY_KEYWORDS['body_parts'].keys()))

        with st.expander("🔍 Filtrowanie Mobility", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                # Filtr 1: Rodzaj
                sel_types = st.multiselect("Rodzaj treningu:", all_types, key="m_types")
            with col2:
                # Filtr 2: Ciało
                sel_body = st.multiselect("Partia ciała:", all_body, key="m_body")
            
            st.markdown("---")
            m_chan_sel = st.multiselect("Instruktor:", m_channels, key="m_chan")
            
            # Wyszukiwarka tekstowa (jako opcja dodatkowa)
            search_query = st.text_input("Szukaj po nazwie (opcjonalne):", key="m_search")
            
            # Czas
            m_dur_range = st.slider("Czas (min):", int(df_mob['duration'].min()), int(df_mob['duration'].max()), (5, 60), key="m_slider")

        # --- LOGIKA FILTROWANIA MOBILITY ---
        df_m_filt = df_mob[
            (df_mob['duration'] >= m_dur_range[0]) & 
            (df_mob['duration'] <= m_dur_range[1])
        ].copy()

        # 1. Filtr Kanału
        if m_chan_sel:
            df_m_filt = df_m_filt[df_m_filt['channel'].isin(m_chan_sel)]
            
        # 2. Filtr Rodzaju (OR logic - pokazuje jeśli ma chociaż jeden z wybranych)
        if sel_types:
            df_m_filt = df_m_filt[df_m_filt['type_tags'].apply(lambda x: bool(set(x) & set(sel_types)))]
            
        # 3. Filtr Ciała (OR logic)
        if sel_body:
            df_m_filt = df_m_filt[df_m_filt['body_tags'].apply(lambda x: bool(set(x) & set(sel_body)))]
            
        # 4. Wyszukiwarka tekstowa
        if search_query:
            df_m_filt = df_m_filt[
                df_m_filt['title'].str.contains(search_query, case=False, na=False) | 
                df_m_filt['description'].str.contains(search_query, case=False, na=False)
            ]
        
        # Sortowanie
        df_m_filt = df_m_filt.sort_values(by='duration')

        st.caption(f"Znaleziono: {len(df_m_filt)}")

        # Lista Mobility
        for _, row in df_m_filt.iterrows():
            with st.container():
                st.markdown("---")
                
                # Tytuł
                st.markdown(f"#### {row['title']}")
                
                # Renderowanie Auto-Tagów
                tags_html = ""
                # Tagi Rodzaju (Niebieskie)
                for t in row['type_tags']:
                    tags_html += f"<span class='mob-tag-type'>{t}</span>"
                # Tagi Ciała (Zielone)
                for t in row['body_tags']:
                    tags_html += f"<span class='mob-tag-body'>{t}</span>"
                
                st.markdown(tags_html + "<br>", unsafe_allow_html=True)
                
                # Info
                st.caption(f"⏱️ **{row['duration']} min** &nbsp;|&nbsp; 📺 {row['channel']}")
                
                # Opis
                desc = str(row.get('description', ''))
                if len(desc) > 150:
                    st.write(desc[:150] + "...")
                elif desc and desc != 'nan':
                    st.write(desc)
                    
                    
                if row['title'] in user_stats['favorites']:
                    label = "Usuń z ulubionych"
                else:
                    label = "Dodaj do ulubionych"
                    
                st.button(
                    label=label,
                    key=f"fav_{row['title']}_{_}",
                    on_click=toggle_favorite,
                    args=(f"{row['title']}",)
                )
                
                if st.button("▶️ Start", key=f"start_{row['title']}_{_}"):
                    increment_usage_stats(row['title'])
                    st.toast(f"Uruchamiam: {row['title']}")
                    
                    js_code = f"""
                    <script>
                    window.open("{row['url']}", "_blank");
                    </script>
                    """
                    components.html(js_code, height=0)