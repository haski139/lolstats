from config import API_KEY
import requests
from bs4 import BeautifulSoup
import time
import json
from collections import Counter

# ==================================
# === KONFIGURACJA GENERATORA ===
# ==================================
headers = {"X-Riot-Token": API_KEY}

# === TWOJA LISTA GRACZY ===
# Wpisz tutaj nazwy pro-graczy, których chcesz znaleźć.
PLAYERS_TO_FIND = [
    "Kiin", "Canyon", "Chovy", "Ruler", "Duro", "Zeus", "Peanut", "Zeka", "Viper", "Delight",
    "Doran", "Oner", "Faker", "Gumayusi", "Keria", "Flandre", "Tarzan", "Shanks", "Hope", "Kael",
    "Bin", "Beichuan", "Shad0w", "Knight", "Elk", "ON", "369", "Kanavi", "Creme", "JackeyLove",
    "fengyue", "Hang", "PerfecT", "Cuzz", "Bdd", "deokdam", "Peter", "Siwoo", "Lucid", "ShowMaker",
    "Aiming", "BeryL", "TheShy", "Wei", "Rookie", "GALA", "Meiko", "Breathe", "Tian", "Xiaohu", "Light", "Crisp"
]

# ==================================
# === NOWA FUNKCJA - WEB SCRAPER ===
# ==================================
def scrape_riot_ids_for_player(player_name):
    """Odwiedza stronę trackingthepros.com i pobiera listę Riot ID dla gracza."""
    print(f"  -> Scrapuję stronę w poszukiwaniu kont dla: {player_name}...")
    # Zamieniamy nazwę na format URL, np. "ShowMaker" -> "showmaker"
    url_player_name = player_name.lower().replace(" ", "")
    url = f"https://www.trackingthepros.com/player/{url_player_name}/"
    
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Szukamy wszystkich Riot ID na stronie. Ten selektor może się zepsuć w przyszłości!
        # Znajdujemy wszystkie linki, które w swoim adresie mają 'riot-id'
        riot_id_elements = soup.select("a[href*='riot-id']")
        
        found_ids = set() # Używamy seta, aby uniknąć duplikatów
        for element in riot_id_elements:
            # Riot ID jest w formacie Nick#Tag, wyciągamy go z tekstu elementu
            full_id = element.get_text(strip=True)
            if '#' in full_id:
                found_ids.add(full_id)
        
        if not found_ids:
            print(f"  -> OSTRZEŻENIE: Nie znaleziono żadnych kont dla {player_name} na stronie.")
            return []
            
        print(f"  -> Znaleziono {len(found_ids)} unikalnych kont.")
        return list(found_ids)

    except requests.exceptions.RequestException as e:
        print(f"  -> BŁĄD: Nie udało się pobrać danych ze strony dla {player_name}. Błąd: {e}")
        return []

# --- Reszta funkcji pomocniczych (API, detekcja roli) - bez zmian ---
def get_puuid(riot_id, tag_line):
    # ... (bez zmian)
    for server in ["asia", "europe", "americas", "sea"]:
        api_url = f"https://{server}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{tag_line}"
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                return response.json()['puuid'], server
        except requests.exceptions.RequestException:
            continue
    return None, None

def get_match_ids(puuid, routing_server, count):
    # ... (bez zmian)
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": count}
    response = requests.get(api_url, headers=headers, params=params)
    if response.status_code == 200: return response.json()
    return None

def get_match_details(match_id, routing_server):
    # ... (bez zmian)
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200: return response.json()
    return None

def detect_main_role(puuid, server):
    # ... (bez zmian)
    match_ids = get_match_ids(puuid, server, 20)
    if not match_ids: return "UNKNOWN"
    roles_played = []
    for match_id in match_ids:
        match_data = get_match_details(match_id, server)
        if match_data and match_data['info']['queueId'] in [420, 440]:
            for p in match_data['info']['participants']:
                if p['puuid'] == puuid and p['individualPosition'] in ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']:
                    roles_played.append(p['individualPosition'])
                    break
        time.sleep(0.05)
    if not roles_played: return "UNKNOWN"
    return Counter(roles_played).most_common(1)[0][0]

# --- GŁÓWNA LOGIKA GENERATORA ---
if __name__ == "__main__":
    final_json_data = {}
    print("--- Rozpoczynam generowanie pliku players.json za pomocą web scrapingu ---")

    for player_name in PLAYERS_TO_FIND:
        print(f"\n--- Przetwarzam gracza: {player_name.upper()} ---")
        
        riot_ids = scrape_riot_ids_for_player(player_name)
        if not riot_ids:
            continue
            
        player_puuids = []
        primary_puuid = None
        primary_server = None

        print("  -> Weryfikuję konta i pobieram PUUID...")
        for full_riot_id in riot_ids:
            riot_id, tag_line = full_riot_id.split('#', 1)
            puuid, server = get_puuid(riot_id, tag_line)
            
            if puuid:
                player_puuids.append(puuid)
                if not primary_puuid:
                    primary_puuid = puuid
                    primary_server = server
            time.sleep(0.1) # Mała przerwa między zapytaniami
        
        if primary_puuid:
            print(f"  -> Wykrywam główną rolę dla {player_name}...")
            role = detect_main_role(primary_puuid, primary_server)
            print(f"  -> Wykryta rola: {role}")

            final_json_data[player_name] = {
                "role": role,
                "accounts": player_puuids
            }
        else:
            print(f"  -> Nie udało się zweryfikować żadnego konta dla {player_name}, pomijam.")
            
    final_json_data["_comment"] = {
        "role": "WZOR_ROLI (np. MIDDLE)",
        "accounts": ["WZOR_PUUID_1", "WZOR_PUUID_2"]
    }

    with open("players.json", "w", encoding="utf-8") as f:
        json.dump(final_json_data, f, indent=2, ensure_ascii=False)

    print("\n--- ✅ Sukces! Plik players.json został wygenerowany. ---")