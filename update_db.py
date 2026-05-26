import pandas as pd
from googleapiclient.discovery import build
import isodate
import os
from dotenv import load_dotenv

load_dotenv()
# --- KONFIGURACJA ---
# Wklej tutaj swój klucz API YouTube
API_KEY = os.getenv("YOUTUBE_API_KEY")

# Lista ID kanałów dla JOGI (przykładowe ID - musisz je podmienić)
YOGA_CHANNELS = [
    "UCITlHzj4MUzRNM17pdWUWeQ", # ID kanału 1
    "UCUVNvkkzMrT4qMhlql2t4iQ", # ID kanału 2
]

# Lista ID kanałów dla MOBILITY (przykładowe ID)
MOBILITY_CHANNELS = [
    "UCIJA9AD3fxbDNwARNBww5mg", # ID kanału 1
]

def get_channel_videos(channel_id):
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    
    # 1. Pobierz ID playlisty "Uploads" dla danego kanału
    ch_req = youtube.channels().list(id=channel_id, part='contentDetails,snippet')
    ch_res = ch_req.execute()
    
    if not ch_res['items']: return []
    
    uploads_playlist_id = ch_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    channel_name = ch_res['items'][0]['snippet']['title']
    print(f"Pobieram z kanału: {channel_name}...")

    # 2. Pobierz filmy z tej playlisty (ostatnie 50)
    # Możesz zwiększyć maxResults, ale 50 na aktualizację zazwyczaj wystarcza
    pl_req = youtube.playlistItems().list(
        playlistId=uploads_playlist_id,
        part='snippet',
        maxResults=50 
    )
    pl_res = pl_req.execute()
    
    video_ids = []
    for item in pl_res['items']:
        video_ids.append(item['snippet']['resourceId']['videoId'])
        
    if not video_ids: return []

    # 3. Pobierz szczegóły filmów (żeby dostać czas trwania)
    vid_req = youtube.videos().list(
        id=','.join(video_ids),
        part='contentDetails,snippet,statistics'
    )
    vid_res = vid_req.execute()
    
    videos_data = []
    for item in vid_res['items']:
        duration_iso = item['contentDetails']['duration']
        duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
        duration_minutes = int(duration_seconds // 60)
        
        # Filtrujemy YouTube Shorts (zazwyczaj < 1 minuty) i bardzo krótkie intro
        if duration_minutes < 2:
            continue

        vid = {
            'title': item['snippet']['title'],
            'channel': channel_name,
            'url': f"https://www.youtube.com/watch?v={item['id']}",
            'duration': duration_minutes,
            'description': item['snippet']['description'].replace("\n", " "),
            'date': item['snippet']['publishedAt'][:10], # YYYY-MM-DD
            # Te pola zostawiamy puste lub domyślne, bo app.py robi to automatycznie
            'category': '', 
            'intensity': 1,
            'props': 'Brak'
        }
        videos_data.append(vid)
        
    return videos_data

def update_csv(filename, channels_list):
    all_new_videos = []
    
    for ch_id in channels_list:
        try:
            vids = get_channel_videos(ch_id)
            all_new_videos.extend(vids)
        except Exception as e:
            print(f"Błąd przy kanale {ch_id}: {e}")

    if not all_new_videos:
        print("Nie znaleziono filmów.")
        return

    df_new = pd.DataFrame(all_new_videos)
    
    # Jeśli plik już istnieje, wczytaj go i połącz (bez duplikatów)
    if os.path.exists(filename):
        df_old = pd.read_csv(filename)
        # Łączymy stare z nowymi
        df_combined = pd.concat([df_new, df_old])
        # Usuwamy duplikaty po URL (żeby nie dodawać tego samego filmu 2 razy)
        df_combined = df_combined.drop_duplicates(subset=['url'], keep='last')
    else:
        df_combined = df_new

    # Zapisz
    df_combined.to_csv(filename, index=False)
    print(f"✅ Zapisano {len(df_combined)} filmów do pliku {filename}")

# --- URUCHOMIENIE ---
if __name__ == "__main__":
    print("--- AKTUALIZACJA BAZY JOGI ---")
    update_csv("yoga_library.csv", YOGA_CHANNELS)
    
    print("\n--- AKTUALIZACJA BAZY MOBILITY ---")
    update_csv("mobility.csv", MOBILITY_CHANNELS)