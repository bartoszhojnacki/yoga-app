import os
import pandas as pd
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PENDING_FILE = "pending.csv"
LIBRARY_FILE = "yoga_library.csv"

# Prompt systemowy
SYSTEM_PROMPT = """
Jesteś ekspertem jogi. Analizujesz filmy z YouTube pod kątem aplikacji fitness.
Dla każdego filmu otrzymasz: Tytuł, Czas, Opis.
Zwróć JSON z polami:
1. "is_practice" (boolean): True tylko jeśli to sesja ćwiczeń. False dla vlogów, zapowiedzi.
2. "tags" (list): Max 4 tagi (np. "Biodra", "Kręgosłup", "Vinyasa", "Relaks", "Siła", "Poranek").
3. "clean_description" (string): 1-2 zdania technicznego opisu (co robimy).
"""

def main():
    if not os.path.exists(PENDING_FILE):
        print("📭 Plik 'pending.csv' nie istnieje. Uruchom najpierw generator.")
        return

    # Wczytaj oczekujące
    try:
        df_pending = pd.read_csv(PENDING_FILE)
        
        # --- POPRAWKA BEZPIECZEŃSTWA ---
        # 1. Usuwamy spacje z nazw kolumn (częsty błąd CSV)
        df_pending.columns = df_pending.columns.str.strip()
        
        # 2. Sprawdzamy, czy kluczowa kolumna istnieje
        if 'title' not in df_pending.columns:
            print(f"❌ BŁĄD STRUKTURY PLIKU CSV!")
            print(f"   Dostępne kolumny: {list(df_pending.columns)}")
            print("   Rozwiązanie: Usuń plik 'pending.csv' i uruchom generator ponownie.")
            return
            
    except pd.errors.EmptyDataError:
        print("📭 Plik 'pending.csv' jest pusty.")
        return

    if df_pending.empty:
        print("📭 Brak filmów do przetworzenia.")
        return

    # Zamiana NaN na pusty string (żeby nie wywalało błędu na pustych opisach)
    df_pending = df_pending.fillna('')

    records = df_pending.to_dict('records')
    print(f"🤖 Rozpoczynam przetwarzanie {len(records)} nowych filmów...")
    
    cleaned_data = []
    BATCH_SIZE = 10 # Przetwarzamy paczkami

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i+BATCH_SIZE]
        print(f"   Processing batch {i} - {i+len(batch)}...")

        # Budowanie promptu
        videos_text = ""
        for idx, v in enumerate(batch):
            # Używamy .get() dla bezpieczeństwa, gdyby brakowało klucza
            title = v.get('title', 'Brak tytułu')
            duration = v.get('duration', 0)
            raw_desc = str(v.get('raw_description', ''))[:400]
            
            videos_text += f"ID: {idx}\nTitle: {title}\nDuration: {duration}\nDesc: {raw_desc}\n---\n"

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Format JSON: {{ 'videos': [ {{ 'id': 0, 'is_practice': true, 'tags': ['Tag1'], 'clean_description': '...' }} ] }}\n\nDATA:\n{videos_text}"}
                ],
                response_format={ "type": "json_object" }
            )
            
            result = json.loads(response.choices[0].message.content)
            ai_results = result.get("videos", [])

            # Łączenie wyników
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
                            "url": original.get("url")
                        })
                        
        except Exception as e:
            print(f"❌ Błąd w paczce (pominąłem ją): {e}")

    # ZAPIS DO BAZY GŁÓWNEJ (Append)
    if cleaned_data:
        df_clean = pd.DataFrame(cleaned_data)
        
        # Tryb append ('a')
        header_mode = not os.path.exists(LIBRARY_FILE)
        df_clean.to_csv(LIBRARY_FILE, mode='a', index=False, header=header_mode, quoting=1)
        
        print(f"\n✅ Sukces! Dodano {len(cleaned_data)} praktyk do '{LIBRARY_FILE}'.")
        
        # CZYSZCZENIE POCZEKALNI
        open(PENDING_FILE, 'w').close() 
        print("🗑️ Wyczyszczono plik 'pending.csv'.")
        
    else:
        print("⚠️ Nie dodano żadnych filmów (błędy lub AI uznało je za nie-praktyki).")

if __name__ == "__main__":
    main()