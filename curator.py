import os
import pandas as pd
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PENDING_FILE = "pending.csv"
LIBRARY_FILE = "yoga_library.csv"

# --- AKTUALIZACJA PROMPTU ---
SYSTEM_PROMPT = """
Jesteś ekspertem jogi. Analizujesz filmy z YouTube pod kątem aplikacji fitness.
Dla każdego filmu otrzymasz: Tytuł, Czas, Opis.
Zwróć JSON z polami:
1. "is_practice" (boolean): True tylko jeśli to sesja ćwiczeń. False dla vlogów, zapowiedzi.
2. "tags" (list): Max 4 tagi (np. "Biodra", "Kręgosłup", "Vinyasa", "Relaks", "Siła", "Poranek").
3. "clean_description" (string): 1-2 zdania technicznego opisu (co robimy).
4. "intensity" (integer): Skala 1-5.
   - 1: Bardzo łagodna (Yin, Nidra, Leżenie, Medytacja w ruchu)
   - 2: Łagodna (Spokojne rozciąganie, Hatha dla początkujących)
   - 3: Umiarkowana (Standardowa Vinyasa, Flow, lekkie wzmacnianie)
   - 4: Wymagająca (Power Yoga, Strong Flow, dłuższe trzymanie trudnych asan)
   - 5: Wysiłkowa (Cardio Yoga, HIIT, "Pot i łzy", Zaawansowane inwersje)
5. "props" (string): Wymień wymagany sprzęt (np. "Klocki", "Pasek", "Wałek"). Jeśli nic nie trzeba (lub tylko mata), wpisz "Brak".
"""

def main():
    if not os.path.exists(PENDING_FILE):
        print("📭 Plik 'pending.csv' nie istnieje.")
        return

    try:
        df_pending = pd.read_csv(PENDING_FILE)
        df_pending.columns = df_pending.columns.str.strip()
        
        if 'title' not in df_pending.columns:
            print("❌ Błąd struktury pliku CSV (brak kolumny title).")
            return
            
    except pd.errors.EmptyDataError:
        print("📭 Plik 'pending.csv' jest pusty.")
        return

    if df_pending.empty:
        print("📭 Brak filmów do przetworzenia.")
        return

    df_pending = df_pending.fillna('')
    records = df_pending.to_dict('records')
    print(f"🤖 Rozpoczynam przetwarzanie {len(records)} filmów (z oceną intensywności)...")
    
    cleaned_data = []
    BATCH_SIZE = 10

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i+BATCH_SIZE]
        print(f"   Processing batch {i} - {i+len(batch)}...")

        videos_text = ""
        for idx, v in enumerate(batch):
            title = v.get('title', 'Brak tytułu')
            duration = v.get('duration', 0)
            raw_desc = str(v.get('raw_description', ''))[:400]
            videos_text += f"ID: {idx}\nTitle: {title}\nDuration: {duration}\nDesc: {raw_desc}\n---\n"

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    # Dodajemy instrukcję struktury JSON uwzględniającą nowe pola
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
                            "title": original.get("title"),
                            "category": ", ".join(ai_res.get("tags", [])),
                            "duration": original.get("duration"),
                            "channel": original.get("channel"),
                            "description": ai_res.get("clean_description"),
                            # --- NOWE POLA ---
                            "intensity": ai_res.get("intensity", 1), # Domyślnie 1 jak AI zgłupieje
                            "props": ai_res.get("props", "Brak"),
                            "url": original.get("url")
                        })
                        
        except Exception as e:
            print(f"❌ Błąd w paczce: {e}")

    if cleaned_data:
        df_clean = pd.DataFrame(cleaned_data)
        header_mode = not os.path.exists(LIBRARY_FILE)
        df_clean.to_csv(LIBRARY_FILE, mode='a', index=False, header=header_mode, quoting=1)
        
        print(f"\n✅ Sukces! Dodano {len(cleaned_data)} praktyk do bazy.")
        open(PENDING_FILE, 'w').close() 
    else:
        print("⚠️ Nie dodano żadnych filmów.")

if __name__ == "__main__":
    main()