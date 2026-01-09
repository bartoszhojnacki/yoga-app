import os
import pandas as pd
import isodate
import re
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")

# --- KONFIGURACJA 1: JOGA (Tu działa AI) ---
YOGA_LIBRARY_FILE = "yoga_library.csv"
PENDING_FILE = "pending.csv"
YOGA_CHANNELS = {
    "Małgorzata Mostowska": "UCITlHzj4MUzRNM17pdWUWeQ",
    "Yoga Home": "UCUVNvkkzMrT4qMhlql2t4iQ",

}

# --- KONFIGURACJA 2: MOBILITY (Tu pobieramy bezpośrednio) ---
MOBILITY_FILE = "mobility.csv"
MOBILITY_CHANNELS = {
     "Malva Stretching":"UCIJA9AD3fxbDNwARNBww5mg"# Przykładowy kanał - zmień na swój!
    # "Tom Merrick": "UCP_kXWao0L0L9b_15aXjE-A"
}

MAX_RESULTS = 1000 

def clean_description(text):
    """Proste czyszczenie opisu dla mobility (usuwa linki i zbędne entery)"""
    text = str(text)
    # Usuń linki http/https
    text = re.sub(r'http\S+', '', text)
    # Zamień wielokrotne spacje/entery na spację
    text = " ".join(text.split())
    return text[:400] # Zwróć pierwsze 400 znaków

def get_existing_ids(filepath, id_col_name='url'):
    ids = set()
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            # Obsługa różnych nazw kolumn w zależności od pliku
            if id_col_name == 'url' and 'url' in df.columns:
                ids.update(df['url'].apply(lambda x: str(x).split('v=')[-1]))
            elif id_col_name == 'video_id' and 'video_id' in df.columns:
                ids.update(df['video_id'].astype(str))
        except:
            pass
    return ids

def fetch_videos(youtube, channels, existing_ids, mode="yoga"):
    """Uniwersalna funkcja pobierająca"""
    new_videos = []
    
    for channel_name, channel_id in channels.items():
        print(f"   🔎 [{mode.upper()}] Skanowanie: {channel_name}...")
        try:
            res_ch = youtube.channels().list(id=channel_id, part='contentDetails').execute()
            if not res_ch['items']: continue
            uploads_id = res_ch['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            request = youtube.playlistItems().list(playlistId=uploads_id, part='snippet', maxResults=50)
            fetched_count = 0
            
            while request and fetched_count < MAX_RESULTS:
                response = request.execute()
                items = response.get('items', [])
                if not items: break

                batch_ids = [item['snippet']['resourceId']['videoId'] for item in items if item['snippet']['resourceId']['videoId'] not in existing_ids]
                fetched_count += len(items)

                if not batch_ids:
                    request = youtube.playlistItems().list_next(request, response)
                    continue

                res_vid = youtube.videos().list(id=','.join(batch_ids), part='snippet,contentDetails').execute()

                for video in res_vid['items']:
                    vid_id = video['id']
                    duration_sec = isodate.parse_duration(video['contentDetails']['duration']).total_seconds()
                    duration_min = int(duration_sec // 60)

                    if duration_min < 2: continue

                    video_data = {
                        "title": video['snippet']['title'],
                        "channel": channel_name,
                        "duration": duration_min,
                        "url": f"https://www.youtube.com/watch?v={vid_id}"
                    }

                    if mode == "yoga":
                        # Dla jogi zachowujemy surowy opis dla AI
                        video_data["video_id"] = vid_id
                        video_data["raw_description"] = video['snippet']['description'].replace("\n", " ")
                    else:
                        # Dla mobility od razu czyścimy opis
                        video_data["description"] = clean_description(video['snippet']['description'])
                        # Dodajemy domyślne tagi, żeby appka nie padła
                        video_data["category"] = "Mobility, Rozciąganie" 
                    
                    new_videos.append(video_data)

                request = youtube.playlistItems().list_next(request, response)
        except Exception as e:
            print(f"      [!] Błąd: {e}")
            
    return new_videos

def main():
    if not API_KEY: return print("❌ Brak API KEY")
    youtube = build('youtube', 'v3', developerKey=API_KEY)

    # 1. PROCES DLA JOGI (Zapis do pending.csv)
    yoga_ids = get_existing_ids(YOGA_LIBRARY_FILE, 'url').union(get_existing_ids(PENDING_FILE, 'video_id'))
    print(f"🧘 Sprawdzam Jogę (w bazie: {len(yoga_ids)})...")
    new_yoga = fetch_videos(youtube, YOGA_CHANNELS, yoga_ids, mode="yoga")
    
    if new_yoga:
        df = pd.DataFrame(new_yoga)
        mode = 'a' if os.path.exists(PENDING_FILE) else 'w'
        df.to_csv(PENDING_FILE, mode=mode, index=False, header=(mode=='w'), quoting=1)
        print(f"✅ Dodano {len(new_yoga)} do pending.csv")
    
    # 2. PROCES DLA MOBILITY (Zapis bezpośrednio do mobility.csv)
    # Tutaj jako ID używamy URL, bo plik ma inną strukturę niż pending
    mobility_ids = get_existing_ids(MOBILITY_FILE, 'url')
    print(f"\n🤸 Sprawdzam Mobility (w bazie: {len(mobility_ids)})...")
    new_mobility = fetch_videos(youtube, MOBILITY_CHANNELS, mobility_ids, mode="mobility")

    if new_mobility:
        df = pd.DataFrame(new_mobility)
        mode = 'a' if os.path.exists(MOBILITY_FILE) else 'w'
        # Zapiszmy z nagłówkiem tylko jeśli plik nie istnieje
        df.to_csv(MOBILITY_FILE, mode=mode, index=False, header=(mode=='w'), quoting=1)
        print(f"✅ Dodano {len(new_mobility)} do mobility.csv (Gotowe do użycia!)")
    else:
        print("💤 Brak nowości w Mobility.")

if __name__ == "__main__":
    main()