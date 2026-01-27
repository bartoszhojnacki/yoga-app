import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
from pyairtable import Api

# --- KONFIGURACJA AIRTABLE ---
try:
    API_KEY = st.secrets["AIRTABLE_API_KEY"]
    BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
    TABLE_NAME = st.secrets["AIRTABLE_TABLE_NAME"]
    api = Api(API_KEY)
    at_table = api.table(BASE_ID, TABLE_NAME)
except Exception:
    at_table = None

st.set_page_config(page_title="Joga & Mobility", page_icon="🧘‍♀️", layout="centered")

# --- CSS ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {padding-top: 1rem; padding-bottom: 3rem;}
            
            .mob-tag-type {background-color: #E3F2FD; color: #0D47A1; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; border: 1px solid #BBDEFB;}
            .mob-tag-body {background-color: #E8F5E9; color: #1B5E20; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; border: 1px solid #C8E6C9;}
            .yoga-tag-style {background-color: #F3E5F5; color: #4A148C; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; border: 1px solid #E1BEE7;}
            .yoga-tag-focus {background-color: #FFF3E0; color: #E65100; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; border: 1px solid #FFE0B2;}
            
            .stTabs [data-baseweb="tab-list"] {gap: 20px;}
            .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px;}
            .stTabs [aria-selected="true"] {background-color: #FF4B4B; color: white;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- SŁOWNIKI ---
MOBILITY_KEYWORDS = {
    "types": {
        "Stretching": ["rozciąganie", "stretching", "stretch", "elastyczność"],
        "Mobility": ["mobilność", "mobility", "zakresy", "ruchomość"],
        "Rolowanie": ["rolowanie", "roller", "rozluźnianie", "automasaż", "piłeczka"],
        "Wzmacnianie": ["wzmacnianie", "siła", "stabilizacja", "aktywacja"]
    },
    "body_parts": {
        "Biodra": ["biodra", "bioder", "miednica", "pośladki", "otwieranie bioder"],
        "Barki & Szyja": ["barki", "barków", "ramiona", "szyja", "kark", "klatka"],
        "Kręgosłup": ["kręgosłup", "plecy", "lędźwi", "grzbiet", "kręgosłupa"],
        "Nogi": ["nogi", "nóg", "uda", "staw skokowy", "stopy", "łydki", "kolana"],
        "Nadgarstki": ["nadgarstki", "dłonie", "przedramiona"],
        "Całe ciało": ["całe ciało", "full body", "ogólne"]
    }
}

YOGA_KEYWORDS = {
    "style": {
        "Spokojna / Yin": ["yin", "spokojna", "relaks", "wieczór", "stres", "sen", "rozciąganie"],
        "Dynamiczna / Vinyasa": ["vinyasa", "power", "flow", "energia", "dynamiczna", "pot"],
        "Poranna": ["dzień dobry", "poranna", "poranek", "rozruch", "pobudzenie"],
        "Dla początkujących": ["początkujących", "podstawy", "łagodna", "prosta"]
    },
    "focus": {
        "Kręgosłup": ["kręgosłup", "plecy", "zdrowy kręgosłup", "odcinek"],
        "Biodra": ["biodra", "bioder", "miednica"],
        "Brzuch / Core": ["brzuch", "core", "mięśnie brzucha", "centrum"],
        "Całe ciało": ["całe ciało", "full body", "ogólno"]
    }
}

# --- FUNKCJE POMOCNICZE (bez zmian logiki) ---
def get_tags_from_text(text, keyword_dict):
    found = []
    text = text.lower()
    for category, keywords in keyword_dict.items():
        if any(k in text for k in keywords):
            found.append(category)
    return found

def auto_tag_mobility(row):
    text = (str(row['title']) + " " + str(row.get('description', ''))).lower()
    return get_tags_from_text(text, MOBILITY_KEYWORDS['types']), get_tags_from_text(text, MOBILITY_KEYWORDS['body_parts'])

def auto_tag_yoga(row):
    text = (str(row['title']) + " " + str(row.get('description', '')) + " " + str(row.get('category', ''))).lower()
    return get_tags_from_text(text, YOGA_KEYWORDS['style']), get_tags_from_text(text, YOGA_KEYWORDS['focus'])

# --- OPTYMALIZACJA 1: CACHE DLA DANYCH ---
# Te funkcje wykonają się TYLKO RAZ na sesję (lub do zmiany CSV)
@st.cache_data
def load_yoga_data():
    try:
        df = pd.read_csv("yoga_library.csv", on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        tags_result = df.apply(auto_tag_yoga, axis=1)
        df['yoga_style'] = tags_result.apply(lambda x: x[0])
        df['yoga_focus'] = tags_result.apply(lambda x: x[1])
        if 'intensity' not in df.columns: df['intensity'] = 1
        else: df['intensity'] = pd.to_numeric(df['intensity'], errors='coerce').fillna(1).astype(int)
        if 'props' not in df.columns: df['props'] = 'Brak'
        else: df['props'] = df['props'].fillna('Brak')
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data
def load_mobility_data():
    try:
        df = pd.read_csv("mobility.csv", on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        tags_result = df.apply(auto_tag_mobility, axis=1)
        df['type_tags'] = tags_result.apply(lambda x: x[0])
        df['body_tags'] = tags_result.apply(lambda x: x[1])
        return df
    except Exception:
        return pd.DataFrame()

# --- OPTYMALIZACJA 2: CACHE DLA AIRTABLE ---
# TTL=300 sekund (5 min), żeby nie pytać bazy przy każdym kliknięciu, chyba że wymusimy update
@st.cache_data(ttl=300)
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
            if fields.get('Favorite'): favs.append(rid)
            cnt = fields.get('Count', 0)
            if cnt > 0: counts[rid] = cnt
        return {"favorites": favs, "usage_count": counts}
    except Exception:
        return {"favorites": [], "usage_count": {}}

def get_airtable_record(title):
    if not at_table: return None
    # Optymalizacja: pobieramy tylko potrzebne pola
    matches = at_table.all(formula=f"{{Title}}='{title}'", max_records=1)
    return matches[0] if matches else None

def toggle_favorite(title):
    if not at_table or not title: return
    record = get_airtable_record(title)
    if record:
        current = record['fields'].get('Favorite', False)
        at_table.update(record['id'], {'Favorite': not current})
    else:
        at_table.create({'Title': title, 'Favorite': True, 'Count': 0})
    load_user_stats.clear() # Czyścimy cache, żeby odświeżyć widok

def increment_usage_stats(title):
    if not at_table or not title: return
    record = get_airtable_record(title)
    if record:
        current = record['fields'].get('Count', 0)
        at_table.update(record['id'], {'Count': current + 1})
    else:
        at_table.create({'Title': title, 'Favorite': False, 'Count': 1})
    # Tutaj NIE czyścimy cache statystyk, żeby nie spowalniać przejścia do wideo
    # Statystyki zaktualizują się przy następnym odświeżeniu strony

# Ładowanie danych (teraz z Cache!)
df_yoga = load_yoga_data()
df_mob = load_mobility_data()
user_stats = load_user_stats()

def render_intensity_html(level):
    try: lvl = max(1, min(int(level), 5))
    except: lvl = 1
    color = "#D32F2F" if lvl >= 4 else "#555"
    return f"<span style='color: {color}; letter-spacing: 1px;'>{'● '*lvl}{'○ '*(5-lvl)}</span>"

# --- UI ---
st.toast(f"Dzień dobry! Pobranych praktyk: {len(df_yoga) + len(df_mob)}", icon="🚀")
st.title("Studio Ruchu")

tab_yoga, tab_mob = st.tabs(["🧘‍♀️ Joga", "🤸‍♂️ Mobility & Stretch"])

# ================= ZAKŁADKA JOGA =================
with tab_yoga:
    if df_yoga.empty:
        st.info("Brak bazy jogi.")
    else:
        # Filtry (bez zmian, cache działa pod spodem)
        all_styles = sorted(list(YOGA_KEYWORDS['style'].keys()))
        all_focus = sorted(list(YOGA_KEYWORDS['focus'].keys()))
        all_channels = sorted(df_yoga['channel'].unique())

        with st.expander("🔍 Filtry Jogi", expanded=True):
            col1, col2 = st.columns(2)
            with col1: sel_styles = st.multiselect("Styl / Energia:", all_styles, key="y_style")
            with col2: sel_focus = st.multiselect("Na co (Cel):", all_focus, key="y_focus")
            
            y_chan = st.multiselect("Kanał:", all_channels, key="y_chan")
            
            TIME_OPTIONS = {"⚡ Do 15 min": (0, 15), "🧘 15-30 min": (15, 30), "💪 30-45 min": (30, 45), "🛌 45+ min": (45, 999)}
            sel_times = st.multiselect("Czas trwania:", list(TIME_OPTIONS.keys()), key="y_time_multi")
            y_intens = st.slider("Trudność:", 1, 5, (1, 5), key="y_int")

        # Logika filtrowania
        df_y_filt = df_yoga.copy()
        if sel_times:
            time_mask = pd.Series([False] * len(df_y_filt))
            for t_label in sel_times:
                t_min, t_max = TIME_OPTIONS[t_label]
                time_mask = time_mask | ((df_y_filt['duration'] >= t_min) & (df_y_filt['duration'] <= t_max))
            df_y_filt = df_y_filt[time_mask]
        
        df_y_filt = df_y_filt[(df_y_filt['intensity'] >= y_intens[0]) & (df_y_filt['intensity'] <= y_intens[1])]
        
        if y_chan: df_y_filt = df_y_filt[df_y_filt['channel'].isin(y_chan)]
        if sel_styles: df_y_filt = df_y_filt[df_y_filt['yoga_style'].apply(lambda x: bool(set(x) & set(sel_styles)))]
        if sel_focus: df_y_filt = df_y_filt[df_y_filt['yoga_focus'].apply(lambda x: bool(set(x) & set(sel_focus)))]

        df_y_filt = df_y_filt.sort_values(by='duration')

        st.caption(f"Wyników: {len(df_y_filt)} (Pokazuję 30 pierwszych)")
        
        # OPTYMALIZACJA 3: Renderujemy tylko pierwsze 30 wyników (Pagination)
        for i, row in df_y_filt.head(30).iterrows():
            with st.container():
                st.markdown("---")
                st.subheader(row['title'])
                tags_html = ""
                for t in row['yoga_style']: tags_html += f"<span class='yoga-tag-style'>{t}</span>"
                for t in row['yoga_focus']: tags_html += f"<span class='yoga-tag-focus'>{t}</span>"
                st.markdown(tags_html + "<br>", unsafe_allow_html=True)
                
                intens_html = render_intensity_html(row['intensity'])
                props_info = f"&nbsp;| 🧱 {row['props']}" if row['props'] != "Brak" else ""
                st.markdown(f"<div style='color:#555; font-size:0.9em; margin:5px 0;'>Trudność: <b>{intens_html}</b>{props_info}<br>📺 {row['channel']} | ⏱️ {row['duration']} min</div>", unsafe_allow_html=True)
                
                desc = str(row['description'])
                if len(desc) > 200:
                    st.write(desc[:200] + "...")
                    with st.expander("Więcej"): st.write(desc)
                else:
                    st.write(desc)

                is_fav = row['title'] in user_stats['favorites']
                fav_label = "❤️ Usuń z ulubionych" if is_fav else "🤍 Dodaj do ulubionych"
                
                col_b1, col_b2 = st.columns([1,1])
                with col_b1:
                    st.button(fav_label, key=f"y_fav_{i}", on_click=toggle_favorite, args=(row['title'],))
                with col_b2:
                    if st.button("▶️ Start", key=f"y_start_{i}"):
                        increment_usage_stats(row['title'])
                        js_code = f"<script>window.open('{row['url']}', '_blank');</script>"
                        components.html(js_code, height=0)

# ================= ZAKŁADKA MOBILITY =================
with tab_mob:
    if df_mob.empty:
        st.info("Brak bazy mobility.")
    else:
        all_types = sorted(list(MOBILITY_KEYWORDS['types'].keys()))
        all_body = sorted(list(MOBILITY_KEYWORDS['body_parts'].keys()))
        m_channels = sorted(df_mob['channel'].unique())

        with st.expander("🔍 Filtrowanie Mobility", expanded=True):
            col1, col2 = st.columns(2)
            with col1: sel_types = st.multiselect("Rodzaj treningu:", all_types, key="m_types")
            with col2: sel_body = st.multiselect("Partia ciała:", all_body, key="m_body")
            
            st.markdown("---")
            m_chan_sel = st.multiselect("Instruktor:", m_channels, key="m_chan")
            search_query = st.text_input("Szukaj po nazwie (opcjonalne):", key="m_search")
            m_dur_range = st.slider("Czas (min):", int(df_mob['duration'].min()), int(df_mob['duration'].max()), (5, 60), key="m_slider")

        df_m_filt = df_mob[
            (df_mob['duration'] >= m_dur_range[0]) & (df_mob['duration'] <= m_dur_range[1])
        ].copy()

        if m_chan_sel: df_m_filt = df_m_filt[df_m_filt['channel'].isin(m_chan_sel)]
        if sel_types: df_m_filt = df_m_filt[df_m_filt['type_tags'].apply(lambda x: bool(set(x) & set(sel_types)))]
        if sel_body: df_m_filt = df_m_filt[df_m_filt['body_tags'].apply(lambda x: bool(set(x) & set(sel_body)))]
        
        if search_query:
            df_m_filt = df_m_filt[
                df_m_filt['title'].str.contains(search_query, case=False, na=False) | 
                df_m_filt['description'].str.contains(search_query, case=False, na=False)
            ]
        
        df_m_filt = df_m_filt.sort_values(by='duration')
        
        # OPTYMALIZACJA 3: Również tutaj limitujemy do 30 wyników
        st.caption(f"Znaleziono: {len(df_m_filt)} (Pokazuję 30 pierwszych)")
        
        for i, row in df_m_filt.head(30).iterrows():
            with st.container():
                st.markdown("---")
                st.subheader(row['title'])
                
                tags_html = ""
                for t in row['type_tags']: tags_html += f"<span class='mob-tag-type'>{t}</span>"
                for t in row['body_tags']: tags_html += f"<span class='mob-tag-body'>{t}</span>"
                st.markdown(tags_html + "<br>", unsafe_allow_html=True)
                
                st.caption(f"⏱️ **{row['duration']} min** &nbsp;|&nbsp; 📺 {row['channel']}")
                desc = str(row.get('description', ''))
                if len(desc) > 150: st.write(desc[:150] + "...")
                
                is_fav = row['title'] in user_stats['favorites']
                fav_label = "❤️ Usuń" if is_fav else "🤍 Dodaj"
                
                col_btn1, col_btn2 = st.columns([1, 1])
                with col_btn1:
                    st.button(fav_label, key=f"m_fav_{i}", on_click=toggle_favorite, args=(row['title'],))
                with col_btn2:
                    if st.button("▶️ Oglądaj", key=f"m_start_{i}"):
                        increment_usage_stats(row['title'])
                        js_code = f"<script>window.open('{row['url']}', '_blank');</script>"
                        components.html(js_code, height=0)