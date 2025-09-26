import requests
import time
import sys
from collections import Counter

# ==================================
# === KONFIGURACJA ===
# ==================================
API_KEY = "RGAPI-8ced64ea-32e7-429d-b190-a9922d4b778d" # Wstaw tutaj swój stały klucz API

# ID kolejek, które chcemy analizować (Solo/Duo, Flex)
DESIRED_QUEUE_IDS = [420, 440]
# Liczba gier do przeszukania
GAMES_TO_FETCH = 50
# Liczba gier do analizy w celu wykrycia głównej roli
GAMES_FOR_ROLE_DETECTION = 20
# Dopuszczalne role
VALID_ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
# Serwery, które program będzie przeszukiwał
ROUTING_SERVERS_TO_TRY = ["asia", "europe", "americas"]

# ==================================
# === FUNKCJE API ===
# ==================================
headers = {"X-Riot-Token": API_KEY}

def get_latest_patch():
    try:
        response = requests.get("https://ddragon.leagueoflegends.com/api/versions.json")
        response.raise_for_status()
        latest_patch = response.json()[0]
        return ".".join(latest_patch.split('.')[:2])
    except requests.exceptions.RequestException as e:
        print(f"BŁĄD: Nie można połączyć się z Data Dragon, aby pobrać patch: {e}")
        return None

def get_puuid(riot_id, tag_line):
    """Przeszukuje wszystkie główne regiony, aby znaleźć gracza."""
    for server in ROUTING_SERVERS_TO_TRY:
        print(f"   -> Sprawdzam serwer: {server}...")
        api_url = f"https://{server}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{tag_line}"
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                print(f"   ✅ Znaleziono gracza na serwerze: {server}")
                return response.json()['puuid'], server
        except requests.exceptions.RequestException:
            continue
    print(f"BŁĄD: Nie znaleziono gracza {riot_id}#{tag_line} na żadnym serwerze.")
    return None, None

def get_match_ids(puuid, routing_server, count):
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": count}
    response = requests.get(api_url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    return None

def get_match_details(match_id, routing_server):
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def detect_main_role(puuid, server):
    print(f"\nAnalizuję ostatnie gry, aby wykryć główną rolę gracza...")
    match_ids = get_match_ids(puuid, server, GAMES_FOR_ROLE_DETECTION)
    if not match_ids:
        return None
    roles_played = []
    for match_id in match_ids:
        match_data = get_match_details(match_id, server)
        if match_data and match_data['info']['queueId'] in DESIRED_QUEUE_IDS:
            for participant in match_data['info']['participants']:
                if participant['puuid'] == puuid:
                    if participant['individualPosition'] in VALID_ROLES:
                        roles_played.append(participant['individualPosition'])
                    break
        time.sleep(0.05)
    if not roles_played:
        return None
    most_common_role = Counter(roles_played).most_common(1)[0][0]
    return most_common_role

# ==================================
# === GŁÓWNA LOGIKA PROGRAMU ===
# ==================================
if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("BŁĄD: Niepoprawna liczba argumentów!")
        print('Sposób użycia 1 (automatyczne wykrywanie roli): python main.py "Nick#Tag"')
        print('Sposób użycia 2 (ręczne podanie roli): python main.py "Nick#Tag" ROLA')
        sys.exit()

    full_riot_id = sys.argv[1]
    if '#' not in full_riot_id:
        print("BŁĄD: Niepoprawny format Riot ID. Użyj formatu \"Nick#Tag\".")
        sys.exit()

    riot_id, tag_line = full_riot_id.split('#')
    
    target_role = None
    if len(sys.argv) == 3:
        manual_role = sys.argv[2].upper()
        if manual_role in VALID_ROLES:
            target_role = manual_role
        else:
            print(f"BŁĄD: '{manual_role}' to niepoprawna rola. Dostępne: {VALID_ROLES}")
            sys.exit()

    print(f"--- Analiza dla gracza: {riot_id}#{tag_line} ---")
    
    current_patch = get_latest_patch()
    if not current_patch:
        sys.exit()

    player_puuid, server = get_puuid(riot_id, tag_line)
    if not player_puuid:
        sys.exit()

    if not target_role:
        target_role = detect_main_role(player_puuid, server)
        if not target_role:
            print("Nie udało się automatycznie wykryć głównej roli gracza. (Możliwy brak gier rankingowych w ostatnim czasie)")
            sys.exit()
        print(f"✅ Automatycznie wykryto główną rolę: {target_role}")

    print(f"\nAktualny patch: {current_patch} | Szukana rola: {target_role}")
    
    match_ids_list = get_match_ids(player_puuid, server, GAMES_TO_FETCH)
    if match_ids_list:
        print(f"Przeszukuję ostatnich {len(match_ids_list)} gier", end="")
        champions_played = []
        for match_id in match_ids_list:
            print(".", end="", flush=True)
            match_data = get_match_details(match_id, server)
            if match_data and match_data['info']['queueId'] in DESIRED_QUEUE_IDS:
                match_patch = ".".join(match_data['info']['gameVersion'].split('.')[:2])
                if match_patch == current_patch:
                    for participant in match_data['info']['participants']:
                        # ===========================================
                        # === TUTAJ JEST POPRAWKA ===
                        # ===========================================
                        if participant['puuid'] == player_puuid and participant['individualPosition'] == target_role:
                            champions_played.append(participant['championName'])
                            break
            time.sleep(0.05)
        
        print("\n\n--- WYNIKI ANALIZY ---")
        if not champions_played:
            print(f"Nie znaleziono gier rankingowych rozegranych przez {riot_id} na pozycji {target_role} na patchu {current_patch}.")
        else:
            champion_counts = Counter(champions_played)
            print(f"Postacie, którymi {riot_id} grał na pozycji {target_role} (patch {current_patch}):")
            for champion, count in champion_counts.most_common():
                print(f"   - {champion}: {count} gier")

    print("\n--- Program zakończył działanie ---")