import os
import pandas as pd
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PENDING_FILE = "pending.csv"
LIBRARY_FILE = "yoga_library.csv"

# --- ZABEZPIECZENIE: Oczekiwane kolumny w pliku pending.csv ---
EXPECTED_COLUMNS = ['video_id', 'title', 'channel', 'duration', 'raw_description', 'url']

# --- SYSTEM PROMPT (bez zmian) ---
SYSTEM_PROMPT = """
Jesteś ekspertem jogi. Analizujesz filmy z YouTube pod kątem aplikacji fitness.
Dla każdego filmu otrzymasz: Tytuł, Czas, Opis.
Zwróć JSON z polami:
1. "is_practice" (boolean): True tylko jeśli to sesja ćwiczeń. False dla vlogów, zapowiedzi.
2. "tags" (list): Max 4 tagi (np. "Biodra", "Kręgosłup", "Vinyasa", "Relaks", "Siła", "Poranek").
3. "clean_description" (string): 1-2 zdania technicznego opisu (co robimy).
4. "intensity" (integer): Skala 1-5.
   - 1: Bardzo łagodna (Yin, Nidra, Leżenie)
   - 2: Łagodna (Spokojne rozciąganie, Hatha dla początkujących)
   - 3: Umiarkowana (Standardowa Vinyasa, Flow)
   - 4: Wymagająca (Power Yoga, Strong Flow)
   - 5: Wysiłkowa (Cardio Yoga, HIIT)
5. "props" (string): Wymień wymagany sprzęt (np. "Klocki", "Pasek"). Jeśli nic nie trzeba, wpisz "Brak".
"""

def main():
    if not os.path.exists(PENDING_FILE):
        print("📭 Plik 'pending.csv' nie istnieje.")
        return

    # --- PANCERNE WCZYTYWANIE ---
    try:
        # Wczytujemy wszystko jako string, żeby uniknąć błędów typów
        df_pending = pd.read_csv(PENDING_FILE, dtype=str)
        
        # 1. Czyszczenie spacji w nagłówkach
        df_pending.columns = df_pending.columns.str.strip()
        
        # 2. Sprawdzenie czy plik nie jest pusty (tylko nagłówek)
        if df_pending.empty:
            print("📭 Plik 'pending.csv' jest pusty (ma tylko nagłówek).")
            return

        # 3. Uzupełnianie brakujących kolumn (gdyby generator coś pomieszał)
        for col in EXPECTED_COLUMNS:
            if col not in df_pending.columns:
                print(f"⚠️ Brak kolumny '{col}' w CSV. Dodaję pustą.")
                df_pending[col] = ""
                
    except pd.errors.EmptyDataError:
        print("📭 Plik 'pending.csv' jest całkowicie pusty.")
        return
    except Exception as e:
        print(f"❌ Krytyczny błąd odczytu CSV: {e}")
        return

    # Konwersja duration na liczby (bo wczytaliśmy jako string)
    df_pending['duration'] = pd.to_numeric(df_pending['duration'], errors='coerce').fillna(0).astype(int)
    df_pending = df_pending.fillna('')
    
    records = df_pending.to_dict('records')
    print(f"🤖 Rozpoczynam przetwarzanie {len(records)} filmów...")
    
    cleaned_data = []
    BATCH_SIZE = 10

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i+BATCH_SIZE]
        print(f"   Processing batch {i} - {i+len(batch)}...")

        videos_text = ""
        for idx, v in enumerate(batch):
            # Teraz mamy pewność, że klucze istnieją, bo wymusiliśmy kolumny
            title = str(v['title'])
            duration = v['duration']
            # Ucinamy opis
            raw_desc = str(v['raw_description'])[:400]
            
            videos_text += f"ID: {idx}\nTitle: {title}\nDuration: {duration}\nDesc: {raw_desc}\n---\n"

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Format JSON: {{ 'videos': [ {{ 'id': 0, 'is_practice': true, 'tags': ['Tag'], 'clean_description': '...', 'intensity': 3, 'props': 'Brak' }} ] }}\n\nDATA:\n{videos_text}"}
                ],
                response_format={ "type": "json_object" }
            )
            
            result = json.loads(response.choices[0].message.content)
            ai_results = result.get("videos", [])

            for ai_res in ai_results:
                batch_id = ai_res.get("id")
                if batch_id is not None and batch_id < len(batch):
                    original = batch[batch_id]
                    
                    if ai_res.get("is_practice", False):
                        cleaned_data.append({
                            "video_id": original.get("video_id"), # Ważne dla deduplikacji
                            "title": original.get("title"),
                            "category": ", ".join(ai_res.get("tags", [])),
                            "duration": original.get("duration"),
                            "channel": original.get("channel"),
                            "description": ai_res.get("clean_description"),
                            "intensity": ai_res.get("intensity", 1),
                            "props": ai_res.get("props", "Brak"),
                            "url": original.get("url")
                        })
                        
        except Exception as e:
            print(f"❌ Błąd AI w paczce {i}: {e}")

    # ZAPIS
    if cleaned_data:
        df_clean = pd.DataFrame(cleaned_data)
        
        # Sprawdzamy czy plik docelowy istnieje, żeby wiedzieć czy pisać nagłówek
        file_exists = os.path.exists(LIBRARY_FILE)
        
        # Tryb 'a' (append)
        df_clean.to_csv(LIBRARY_FILE, mode='a', index=False, header=not file_exists, quoting=1)
        
        print(f"\n✅ Sukces! Dodano {len(cleaned_data)} nowych praktyk.")
        
        # Czyścimy pending
        open(PENDING_FILE, 'w').close()
        print("🗑️ Wyczyszczono pending.csv")
    else:
        print("⚠️ Nie dodano żadnych filmów (błędy lub brak praktyk).")
        # Opcjonalnie: też wyczyść pending, jeśli to same śmieci/vlogi, żeby nie mieliło ich w kółko
        # open(PENDING_FILE, 'w').close() 

if __name__ == "__main__":
    main()