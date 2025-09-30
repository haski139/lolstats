import time
import json
from collections import Counter
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests

# ==================================
# === KONFIGURACJA GENERATORA ===
# ==================================
from config import API_KEY 
headers = {"X-Riot-Token": API_KEY}

PLAYERS_TO_FIND = [
    "Kiin", "Canyon", "Chovy", "Ruler", "Duro", "Zeus", "Peanut", "Zeka", "Viper", "Delight",
    "Doran", "Oner", "Faker", "Gumayusi", "Keria", "Flandre", "Tarzan", "Shanks", "Hope", "Kael",
    "Bin", "Beichuan", "Shad0w", "Knight", "Elk", "ON", "369", "Kanavi", "Creme", "JackeyLove",
    "fengyue", "Hang", "PerfecT", "Cuzz", "Bdd", "deokdam", "Peter", "Siwoo", "Lucid", "ShowMaker",
    "Aiming", "BeryL", "TheShy", "Wei", "Rookie", "GALA", "Meiko", "Breathe", "Tian", "Xiaohu", "Light", "Crisp"
]
# NOWOŚĆ: Nazwa nowego pliku wyjściowego
OUTPUT_JSON_FILE = "players2.json"

# ==================================
# === FUNKCJA SCRAPUJĄCA (Twoja wersja) ===
# ==================================
def scrape_player_data_with_uc(player_name):
    """Pobiera listę kont ORAZ rolę gracza bezpośrednio ze strony."""
    print(f"  -> Uruchamiam przeglądarkę Brave w tle dla: {player_name}...")
    url = f"https://www.trackingthepros.com/player/{player_name.lower().replace(' ', '')}/"
    
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    
    # === WSKAZUJEMY ŚCIEŻKĘ DO BRAVE ===
    browser_path = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe" # <-- UPEWNIJ SIĘ, ŻE TO TWOJA ŚCIEŻKA
    
    driver = uc.Chrome(options=options, browser_executable_path=browser_path)
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.XPATH, "//h4[text()='Accounts']")))
        
        player_role = "UNKNOWN"
        try:
            role_element = driver.find_element(By.XPATH, "//table//tr[td[text()='Role']]/td[2]")
            player_role = role_element.text.strip().upper()
            if player_role == "UTILITY":
                player_role = "SUPPORT"
        except: pass

        try:
            driver.execute_script("showInactive()")
            time.sleep(1)
        except Exception: pass 

        account_rows = driver.find_elements(By.XPATH, "//div[h4[text()='Accounts']]/table/tbody/tr")
        found_ids = set()
        for row in account_rows:
            try:
                full_id_text = row.find_element(By.XPATH, ".//td[1]").text.strip()
                full_id = full_id_text.split(']', 1)[-1].strip()
                if '#' in full_id:
                    found_ids.add(full_id)
            except: continue

        if not found_ids:
             return [], player_role

        print(f"  -> Znaleziono {len(found_ids)} unikalnych kont.")
        return list(found_ids), player_role
    
    except Exception as e:
        print(f"  -> KRYTYCZNY BŁĄD podczas scrapowania dla {player_name}: {e}")
        driver.save_screenshot('debug_screenshot.png')
        return [], "UNKNOWN"
    finally:
        driver.quit()

# ==================================
# === POPRAWIONA FUNKCJA WERYFIKACYJNA ===
# ==================================
def get_puuid(riot_id, tag_line):
    """Cierpliwie przeszukuje wszystkie regiony, aż znajdzie konto."""
    for server in ["asia", "europe", "americas", "sea"]:
        api_url = f"https://{server}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{tag_line}"
        try:
            r = requests.get(api_url, headers=headers)
            if r.status_code == 200:
                return r.json()['puuid'], server
        except requests.exceptions.RequestException:
            continue 
    return None, None

# --- GŁÓWNA LOGIKA GENERATORA ---
if __name__ == "__main__":
    final_json_data = {}
    print(f"--- Rozpoczynam generowanie ulepszonego pliku {OUTPUT_JSON_FILE} ---")
    for player_name in PLAYERS_TO_FIND:
        print(f"\n--- Przetwarzam gracza: {player_name.upper()} ---")
        
        riot_ids, role = scrape_player_data_with_uc(player_name)
        
        if not riot_ids and role == "UNKNOWN":
            continue
        
        # ZMIANA: Będziemy tu przechowywać pary [puuid, serwer]
        player_accounts_data = [] 
        print(f"  -> Weryfikuję {len(riot_ids)} kont...")
        
        for full_riot_id in riot_ids:
            if '#' not in full_riot_id.strip(): continue
            riot_id, tag_line = full_riot_id.strip().split('#', 1)
            puuid, server = get_puuid(riot_id, tag_line)
            if puuid:
                # Zapisujemy parę zamiast samego puuid
                player_accounts_data.append([puuid, server]) 
            time.sleep(0.1)
            
        if player_accounts_data:
            print(f"  -> Pomyślnie zweryfikowano {len(player_accounts_data)} z {len(riot_ids)} kont.")
            final_json_data[player_name] = {"role": role, "accounts": player_accounts_data}
        else:
            print(f"  -> Nie udało się zweryfikować żadnego konta dla {player_name}, pomijam.")
    
    final_json_data["_comment"] = { "role": "WZOR_ROLI", "accounts": [["WZOR_PUUID_1", "serwer"]] }
    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(final_json_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n\n--- ✅ Sukces! Plik {OUTPUT_JSON_FILE} został wygenerowany. ---")