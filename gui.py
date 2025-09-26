from config import API_KEY
import customtkinter
import requests
import time
import sys
from collections import Counter
import threading
import sqlite3
import json

# ==================================
# === KONFIGURACJA APLIKACJI ===
# ==================================

DB_FILE = "match_cache.db"
GAMES_TO_FETCH = 100
DESIRED_QUEUE_IDS = [420, 440]
GAMES_FOR_ROLE_DETECTION = 20
VALID_ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
ROUTING_SERVERS_TO_TRY = ["asia", "europe", "americas"]
headers = {"X-Riot-Token": API_KEY}

# =================================================================
# === BAZA DANYCH (CACHE) i SILNIK APLIKACJI ===
# (Te funkcje pozostają bez zmian - nasza solidna podstawa)
# =================================================================

def cleanup_old_cache():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    two_weeks_ago = int(time.time()) - (14 * 24 * 60 * 60)
    cursor.execute("DELETE FROM matches_cache WHERE timestamp < ?", (two_weeks_ago,))
    conn.commit()
    conn.close()

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches_cache (
            match_id TEXT PRIMARY KEY,
            match_data TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    cleanup_old_cache()

def get_latest_patch():
    try:
        response = requests.get("https://ddragon.leagueoflegends.com/api/versions.json")
        response.raise_for_status()
        latest_patch = response.json()[0]
        return ".".join(latest_patch.split('.')[:2])
    except requests.exceptions.RequestException: return None

def get_puuid(riot_id, tag_line):
    for server in ROUTING_SERVERS_TO_TRY:
        api_url = f"https://{server}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{tag_line}"
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                return response.json()['puuid'], server
        except requests.exceptions.RequestException: continue
    return None, None

def get_match_ids(puuid, routing_server, count):
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": count}
    response = requests.get(api_url, headers=headers, params=params)
    if response.status_code == 200: return response.json()
    return None

def get_match_details(match_id, routing_server):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT match_data FROM matches_cache WHERE match_id = ?", (match_id,))
    cached_result = cursor.fetchone()
    if cached_result:
        conn.close()
        return json.loads(cached_result[0])
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        match_data = response.json()
        cursor.execute("INSERT OR REPLACE INTO matches_cache (match_id, match_data, timestamp) VALUES (?, ?, ?)",
                       (match_id, json.dumps(match_data), int(time.time())))
        conn.commit()
        conn.close()
        return match_data
    conn.close()
    return None

def detect_main_role(puuid, server, log_message_callback):
    log_message_callback(f"\nAnalizuję ostatnie gry, aby wykryć główną rolę gracza...")
    match_ids = get_match_ids(puuid, server, GAMES_FOR_ROLE_DETECTION)
    if not match_ids: return None
    roles_played = []
    for match_id in match_ids:
        match_data = get_match_details(match_id, server)
        if match_data and match_data['info']['queueId'] in DESIRED_QUEUE_IDS:
            for participant in match_data['info']['participants']:
                if participant['puuid'] == puuid and participant['individualPosition'] in VALID_ROLES:
                    roles_played.append(participant['individualPosition'])
                    break
        time.sleep(0.05)
    if not roles_played: return None
    return Counter(roles_played).most_common(1)[0][0]

# =================================================================
# === LOGIKA INTERFEJSU GRAFICZNEGO (GUI) ===
# =================================================================

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        setup_database()
        self.title("Pro-Stats Tracker by Haski")
        self.geometry("800x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- Zmiany w widgetach ---
        self.top_frame = customtkinter.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.top_frame.grid_columnconfigure(0, weight=1)

        self.label = customtkinter.CTkLabel(self.top_frame, text="Wpisz Riot ID graczy (oddzielone przecinkami):")
        self.label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")

        self.riot_id_entry = customtkinter.CTkEntry(self.top_frame, placeholder_text="Nick1#Tag1, Nick2#Tag2, ...")
        self.riot_id_entry.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.analyze_button = customtkinter.CTkButton(self.top_frame, text="Analizuj", command=self.start_analysis_thread)
        self.analyze_button.grid(row=1, column=1, padx=10, pady=10)

        # NOWOŚĆ: Checkbox do opcji TOP 3
        self.top3_checkbox_var = customtkinter.IntVar()
        self.top3_checkbox = customtkinter.CTkCheckBox(self.top_frame, text="Pokaż tylko Top 3", variable=self.top3_checkbox_var)
        self.top3_checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=(0,10), sticky="w")
        
        self.output_textbox = customtkinter.CTkTextbox(self, state="disabled", font=("Consolas", 14))
        self.output_textbox.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")

    def log_message(self, message):
        self.output_textbox.configure(state="normal")
        self.output_textbox.insert("end", message + "\n")
        self.output_textbox.configure(state="disabled")
        self.output_textbox.see("end")

    def start_analysis_thread(self):
        self.analyze_button.configure(state="disabled", text="Analizuję...")
        self.output_textbox.configure(state="normal")
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.configure(state="disabled")
        analysis_thread = threading.Thread(target=self.run_analysis)
        analysis_thread.start()

    def run_analysis(self):
        """ULEPSZONA FUNKCJA: Główna pętla analityczna dla wielu graczy."""
        player_inputs = [p.strip() for p in self.riot_id_entry.get().split(',')]
        if not player_inputs or not player_inputs[0]:
            self.log_message("BŁĄD: Nie wpisano żadnego gracza.")
            self.analyze_button.configure(state="normal", text="Analizuj")
            return
            
        current_patch = get_latest_patch()
        if not current_patch:
            self.log_message("BŁĄD: Nie udało się pobrać numeru patcha.")
            self.analyze_button.configure(state="normal", text="Analizuj")
            return
        
        combined_champion_counts = Counter()

        for full_riot_id in player_inputs:
            if '#' not in full_riot_id:
                self.log_message(f"\n--- Pominięto: '{full_riot_id}' (niepoprawny format) ---")
                continue
            
            riot_id, tag_line = full_riot_id.split('#')
            self.log_message(f"\n--- Analiza dla gracza: {riot_id}#{tag_line} ---")
            self.log_message(f"Aktualny patch: {current_patch}")
            
            player_puuid, server = get_puuid(riot_id, tag_line)
            if not player_puuid:
                self.log_message(f"BŁĄD: Nie znaleziono gracza {riot_id}#{tag_line}.")
                continue
            
            target_role = detect_main_role(player_puuid, server, self.log_message)
            if not target_role:
                self.log_message("Nie udało się automatycznie wykryć głównej roli.")
                continue
            self.log_message(f"✅ Wykryto główną rolę: {target_role}")

            match_ids_list = get_match_ids(player_puuid, server, GAMES_TO_FETCH)
            if match_ids_list:
                self.log_message(f"Przeszukuję ostatnich {len(match_ids_list)} gier...")
                champions_played = []
                for match_id in match_ids_list:
                    match_data = get_match_details(match_id, server)
                    if match_data and match_data['info']['queueId'] in DESIRED_QUEUE_IDS:
                        match_patch = ".".join(match_data['info']['gameVersion'].split('.')[:2])
                        if match_patch == current_patch:
                            for p in match_data['info']['participants']:
                                if p['puuid'] == player_puuid and p['individualPosition'] == target_role:
                                    champions_played.append(p['championName'])
                    time.sleep(0.01)
                
                if champions_played:
                    champion_counts = Counter(champions_played)
                    combined_champion_counts.update(champion_counts) # Dodajemy wyniki do łącznych statystyk
                    
                    self.log_message(f"\nWyniki dla {riot_id} (rola: {target_role}):")
                    
                    # Logika wyświetlania Top 3 lub wszystkich
                    limit = 3 if self.top3_checkbox_var.get() == 1 else None
                    for champion, count in champion_counts.most_common(limit):
                        self.log_message(f"   - {champion}: {count} gier")
                else:
                    self.log_message(f"Nie znaleziono gier na patchu {current_patch} dla {riot_id} na roli {target_role}.")

        # --- Wyświetlanie łącznego podsumowania ---
        self.log_message("\n\n=============================================")
        self.log_message("--- ŁĄCZNE PODSUMOWANIE (WSZYSCY GRACZE) ---")
        self.log_message("=============================================")
        if not combined_champion_counts:
            self.log_message("Brak danych do stworzenia podsumowania.")
        else:
            limit = 3 if self.top3_checkbox_var.get() == 1 else None
            for champion, count in combined_champion_counts.most_common(limit):
                self.log_message(f"   - {champion}: {count} gier")

        self.analyze_button.configure(state="normal", text="Analizuj")

# --- Uruchomienie Aplikacji ---
if __name__ == "__main__":
    app = App()
    app.mainloop()