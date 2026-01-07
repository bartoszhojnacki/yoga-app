import os
import pandas as pd
import isodate
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# --- KONFIGURACJA ---
API_KEY = os.getenv("YOUTUBE_API_KEY")
LIBRARY_FILE = "yoga_library.csv" # Baza główna (gotowe)
PENDING_FILE = "pending.csv"      # Poczekalnia (do przetworzenia)

CHANNELS = {
    "Małgorzata Mostowska": "UCITlHzj4MUzRNM17pdWUWeQ",
    "Yoga Home": "UCUVNvkkzMrT4qMhlql2t4iQ",
    # "Basia Tworek": "UCpqYY3zU3PbEPZ_7P-woiAw",
    # Dodaj nowy kanał tu - skrypt pobierze z niego tylko nowości (lub wszystko przy 1. uruchomieniu)
}

MAX_RESULTS_PER_CHANNEL = 1000 # Sprawdzamy ostanie 50 filmów (czy nie pojawiło się coś nowego)

def get_existing_video_ids():
    """Tworzy zbiór ID filmów, które już mamy (w bazie lub w poczekalni)."""
    ids = set()
    
    # 1. Sprawdź bibliotekę główną
    if os.path.exists(LIBRARY_FILE):
        try:
            df = pd.read_csv(LIBRARY_FILE)
            if 'url' in df.columns:
                # Wyciągamy ID z URL (np. watch?v=XYZ -> XYZ)
                ids.update(df['url'].apply(lambda x: x.split('v=')[-1]))
        except Exception:
            pass

    # 2. Sprawdź poczekalnię
    if os.path.exists(PENDING_FILE):
        try:
            df = pd.read_csv(PENDING_FILE)
            if 'video_id' in df.columns:
                ids.update(df['video_id'])
        except Exception:
            pass
            
    return ids

def main():
    if not API_KEY:
        print("❌ BŁĄD: Brak klucza API w pliku .env")
        return

    youtube = build('youtube', 'v3', developerKey=API_KEY)
    
    existing_ids = get_existing_video_ids()
    print(f"📚 W bazie mamy już {len(existing_ids)} unikalnych filmów. Szukam nowości...")

    new_videos = []

    for channel_name, channel_id in CHANNELS.items():
        print(f"   🔎 Skanowanie: {channel_name}...")
        
        try:
            # 1. ID playlisty Uploads
            res_channel = youtube.channels().list(id=channel_id, part='contentDetails').execute()
            if not res_channel['items']:
                print(f"      [!] Nie znaleziono kanału {channel_id}")
                continue
            uploads_id = res_channel['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # 2. Pobieranie listy (z paginacją, jeśli trzeba, tu uproszczone do limitu sprawdzenia)
            # Zwykle wystarczy sprawdzić ostatnie X filmów, żeby wyłapać nowości
            request = youtube.playlistItems().list(
                playlistId=uploads_id,
                part='snippet',
                maxResults=MAX_RESULTS_PER_CHANNEL
            )
            
            while request and len(new_videos) < 500: # Bezpiecznik pętli
                response = request.execute()
                
                # Zbieramy ID do sprawdzenia detali
                batch_ids = []
                for item in response['items']:
                    vid_id = item['snippet']['resourceId']['videoId']
                    if vid_id not in existing_ids:
                        batch_ids.append(vid_id)
                
                if not batch_ids:
                    # Jeśli cała paczka 50 filmów jest już w bazie, to znaczy, 
                    # że doszliśmy do starych filmów -> przerywamy dla tego kanału
                    print("      ...ta paczka jest już w bazie, pobieram starszą stronę...") ### DO BACKFILLU
                    request = youtube.playlistItems().list_next(request, response) ### DO BACKFILLU
                    continue ### DO BACKFILLU
                    # break ### ODKOMENTOWAĆ JAK NIE CHCEMY B
                
                # 3. Pobieranie detali TYLKO dla nowych ID
                res_videos = youtube.videos().list(
                    id=','.join(batch_ids),
                    part='snippet,contentDetails'
                ).execute()

                for video in res_videos['items']:
                    vid_id = video['id']
                    
                    # Parsowanie czasu
                    duration_iso = video['contentDetails']['duration']
                    duration_sec = isodate.parse_duration(duration_iso).total_seconds()
                    duration_min = int(duration_sec // 60)
                    
                    if duration_min < 5: # Ignoruj bardzo krótkie (poniżej 5 min)
                        continue

                    new_videos.append({
                        "video_id": vid_id, # Ważne dla deduplikacji
                        "title": video['snippet']['title'],
                        "channel": channel_name,
                        "duration": duration_min,
                        "raw_description": video['snippet']['description'].replace("\n", " "),
                        "url": f"https://www.youtube.com/watch?v={vid_id}"
                    })

                # Paginacja
                request = youtube.playlistItems().list_next(request, response)
                
        except Exception as e:
            print(f"      [!] Błąd kanału: {e}")

    # Zapis do pending.csv (Dopisujemy nowe, nie nadpisujemy starych w pending)
    if new_videos:
        df_new = pd.DataFrame(new_videos)
        
        # Jeśli plik istnieje, dopisz bez nagłówka, jeśli nie - stwórz z nagłówkiem
        header_mode = not os.path.exists(PENDING_FILE)
        df_new.to_csv(PENDING_FILE, mode='a', index=False, header=header_mode, quoting=1)
        
        print(f"\n✅ Dodano {len(new_videos)} nowych filmów do '{PENDING_FILE}'.")
        print("👉 Uruchom teraz 'curator.py', aby przetworzyć je przez AI.")
    else:
        print("\n💤 Brak nowych filmów. Twoja biblioteka jest aktualna.")

if __name__ == "__main__":
    main()