import os
import pandas as pd
import isodate
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# --- KONFIGURACJA ---
API_KEY = os.getenv("YOUTUBE_API_KEY")
LIBRARY_FILE = "yoga_library.csv" 
PENDING_FILE = "pending.csv"      

CHANNELS = {
    "Małgorzata Mostowska": "UCITlHzj4MUzRNM17pdWUWeQ",
    "Yoga Home": "UCUVNvkkzMrT4qMhlql2t4iQ",
    "Malva Stretching":"UCIJA9AD3fxbDNwARNBww5mg"

}

# TERAZ TO ZADZIAŁA: Pobierze do 1000 filmów z KAŻDEGO kanału
MAX_RESULTS_PER_CHANNEL = 1000 

def get_existing_video_ids():
    ids = set()
    # Sprawdź bibliotekę główną
    if os.path.exists(LIBRARY_FILE):
        try:
            df = pd.read_csv(LIBRARY_FILE)
            if 'url' in df.columns:
                ids.update(df['url'].apply(lambda x: str(x).split('v=')[-1]))
        except Exception:
            pass
    # Sprawdź poczekalnię
    if os.path.exists(PENDING_FILE):
        try:
            df = pd.read_csv(PENDING_FILE)
            if 'video_id' in df.columns:
                ids.update(df['video_id'].astype(str))
        except Exception:
            pass  
    return ids

def main():
    if not API_KEY:
        print("❌ BŁĄD: Brak klucza API w pliku .env")
        return

    youtube = build('youtube', 'v3', developerKey=API_KEY)
    
    existing_ids = get_existing_video_ids()
    print(f"📚 W bazie mamy już {len(existing_ids)} filmów. Szukam reszty...")

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

            # 2. Inicjalizacja pętli dla kanału
            request = youtube.playlistItems().list(
                playlistId=uploads_id,
                part='snippet',
                maxResults=50 # To max na jedno zapytanie API
            )
            
            channel_fetched_count = 0 # Licznik dla obecnego kanału
            
            # PĘTLA: Dopóki API daje wyniki I nie przekroczyliśmy limitu na kanał
            while request and channel_fetched_count < MAX_RESULTS_PER_CHANNEL:
                response = request.execute()
                items = response.get('items', [])
                
                if not items:
                    break
                
                # Zbieramy ID z tej strony (page)
                batch_ids_to_fetch = []
                
                for item in items:
                    vid_id = item['snippet']['resourceId']['videoId']
                    
                    # Jeśli filmu nie ma w bazie -> dodajemy do listy "do pobrania detali"
                    if vid_id not in existing_ids:
                        batch_ids_to_fetch.append(vid_id)
                
                # Zwiększamy licznik przetworzonych (nawet jeśli już je mamy, to "przeskanowaliśmy" je)
                channel_fetched_count += len(items)

                # Jeśli cała paczka (50) jest już w bazie, ale chcemy szukać głębiej (backfill),
                # to NIE przerywamy, tylko idziemy do następnej strony.
                if not batch_ids_to_fetch:
                    # print(f"      ...strona pusta lub już w bazie, idę dalej ({channel_fetched_count}/{MAX_RESULTS_PER_CHANNEL})")
                    request = youtube.playlistItems().list_next(request, response)
                    continue
                
                # 3. Pobieranie detali (czas trwania) dla nowych ID
                res_videos = youtube.videos().list(
                    id=','.join(batch_ids_to_fetch),
                    part='snippet,contentDetails'
                ).execute()

                for video in res_videos['items']:
                    vid_id = video['id']
                    
                    duration_iso = video['contentDetails']['duration']
                    duration_sec = isodate.parse_duration(duration_iso).total_seconds()
                    duration_min = int(duration_sec // 60)
                    
                    # Filtr długości (np. odrzucamy < 2 min)
                    if duration_min < 2: 
                        continue

                    new_videos.append({
                        "video_id": vid_id,
                        "title": video['snippet']['title'],
                        "channel": channel_name,
                        "duration": duration_min,
                        "raw_description": video['snippet']['description'].replace("\n", " "),
                        "url": f"https://www.youtube.com/watch?v={vid_id}"
                    })

                print(f"      ...pobrano partię. Znaleziono nowych: {len(new_videos)} (Przeskanowano na kanale: {channel_fetched_count})")
                
                # Następna strona
                request = youtube.playlistItems().list_next(request, response)
                
        except Exception as e:
            print(f"      [!] Błąd kanału: {e}")

    # Zapis do pending.csv
    if new_videos:
        df_new = pd.DataFrame(new_videos)
        
        # Jeśli plik istnieje, dopisz. Jeśli nie - stwórz.
        header_mode = not os.path.exists(PENDING_FILE)
        df_new.to_csv(PENDING_FILE, mode='a', index=False, header=header_mode, quoting=1)
        
        print(f"\n✅ SKOŃCZONE! Dodano {len(new_videos)} nowych filmów do '{PENDING_FILE}'.")
    else:
        print("\n💤 Brak nowych filmów do dodania.")

if __name__ == "__main__":
    main()