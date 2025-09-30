import customtkinter
import requests
import time
from collections import Counter
import threading
import sqlite3
import json
import os 
import sys 
import asyncio # <--- DODAJ TĘ LINIJKĘ (jeśli jej nie ma)
import aiohttp # <--- TA LINIJKA TEŻ POWINNA BYĆ

# ==================================
# === NOWOŚĆ: INTELIGENTNE ZNAJDOWANIE PLIKÓW ===
# ==================================
def resource_path(relative_path):
    """ Zwraca poprawną ścieżkę do zasobu, działa zarówno w trybie .py jak i .exe """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ... (reszta kodu pozostaje bez zmian) ...

# ==================================
# === KONFIGURACJA APLIKACJI ===
# ==================================
from config import API_KEY

# Używamy naszej nowej funkcji do tworzenia ścieżek
DB_FILE = resource_path("match_cache.db")
PLAYERS_FILE = resource_path("players.json") 
DESIRED_QUEUE_IDS = [420, 440]
RIOT_API_HEADERS = {"X-Riot-Token": API_KEY}
ROUTING_SERVERS_TO_TRY = ["americas", "europe", "asia", "sea"]

PROFESSIONAL_PLAYERS_DB = {}

# ... (reszta kodu, wszystkie funkcje i klasa App, pozostaje DOKŁADNIE taka sama) ...
# Poniżej wklejony jest cały, kompletny i działający kod.

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS matches_cache (match_id TEXT PRIMARY KEY, match_data TEXT NOT NULL, timestamp INTEGER NOT NULL)")
    conn.commit()
    conn.close()

def load_pro_players_database(log_message_callback):
    global PROFESSIONAL_PLAYERS_DB
    try:
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            PROFESSIONAL_PLAYERS_DB = json.load(f)
        log_message_callback(f"✅ Baza danych {len(PROFESSIONAL_PLAYERS_DB) - 1} pro-graczy załadowana.")
    except FileNotFoundError:
        log_message_callback(f"OSTRZEŻENIE: Nie znaleziono pliku '{PLAYERS_FILE}'.")
    except Exception as e:
        log_message_callback(f"BŁĄD: Nie udało się wczytać pliku {PLAYERS_FILE}. Błąd: {e}")

async def get_puuid_by_riot_id(session, riot_id, tag_line):
    for server in ROUTING_SERVERS_TO_TRY:
        api_url = f"https://{server}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{tag_line}"
        try:
            async with session.get(api_url, headers=RIOT_API_HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    return [[data['puuid'], server]]
        except: continue
    return None

async def get_match_ids(session, puuid, routing_server, count=100):
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": count}
    try:
        async with session.get(api_url, headers=RIOT_API_HEADERS, params=params) as response:
            if response.status == 200: return await response.json()
    except: return None
    return None

async def get_match_details(session, match_id, routing_server):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT match_data FROM matches_cache WHERE match_id = ?", (match_id,))
    cached = cursor.fetchone()
    if cached:
        conn.close()
        return json.loads(cached[0])
    
    api_url = f"https://{routing_server}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    try:
        async with session.get(api_url, headers=RIOT_API_HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                cursor.execute("INSERT OR REPLACE INTO matches_cache (match_id, match_data, timestamp) VALUES (?, ?, ?)",
                               (match_id, json.dumps(data), int(time.time())))
                conn.commit()
                conn.close()
                return data
    except: pass
    conn.close()
    return None

# =================================================================
# === GŁÓWNA KLASA APLIKACJI (GUI) ===
# =================================================================

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        setup_database()
        self.title("Pro-Stats Tracker by Haski (v7.2 - Final Fix)")
        self.geometry("800x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.top_frame = customtkinter.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.top_frame.grid_columnconfigure(0, weight=1)
        self.player_entry = customtkinter.CTkEntry(self.top_frame, placeholder_text="Wpisz nicki graczy oddzielone przecinkami...")
        self.player_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.player_entry.bind("<Return>", self.start_analysis_thread_event)
        self.analyze_button = customtkinter.CTkButton(self.top_frame, text="Analizuj", command=self.start_analysis_thread)
        self.analyze_button.grid(row=0, column=1, padx=10, pady=10)
        self.options_frame = customtkinter.CTkFrame(self)
        self.options_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.top3_checkbox_var = customtkinter.IntVar()
        self.top3_checkbox = customtkinter.CTkCheckBox(self.options_frame, text="Pokaż tylko Top 3", variable=self.top3_checkbox_var)
        self.top3_checkbox.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.output_textbox = customtkinter.CTkTextbox(self, state="disabled", font=("Consolas", 14))
        self.output_textbox.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        load_pro_players_database(self.log_message)

    def log_message(self, message, clear=False):
        self.output_textbox.configure(state="normal")
        if clear: self.output_textbox.delete("1.0", "end")
        self.output_textbox.insert("end", message + "\n")
        self.output_textbox.configure(state="disabled")
        self.output_textbox.see("end")
    
    def start_analysis_thread_event(self, event):
        self.start_analysis_thread()

    def start_analysis_thread(self):
        self.analyze_button.configure(state="disabled", text="Analizuję...")
        threading.Thread(target=self.run_async_analysis, daemon=True).start()

    def run_async_analysis(self):
        try:
            asyncio.run(self.main_analysis())
        except Exception as e:
            self.log_message(f"BŁĄD KRYTYCZNY: {e}")
            self.analyze_button.configure(state="normal", text="Analizuj")

    def find_pro_player_data(self, player_handle):
        handle_lower = player_handle.lower()
        for key, data in PROFESSIONAL_PLAYERS_DB.items():
            if key.lower() == handle_lower:
                return data, key
        return None, None

    async def main_analysis(self):
        self.log_message("", clear=True)
        user_input = self.player_entry.get().strip()
        if not user_input:
            self.log_message("BŁĄD: Pole wyszukiwania jest puste.")
            self.analyze_button.configure(state="normal", text="Analizuj")
            return

        player_inputs = [p.strip() for p in user_input.split(',')]
        current_patch = ".".join(requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0].split('.')[:2])
        self.log_message(f"Aktualny patch: {current_patch}\n")
        
        combined_champion_counts = Counter()

        async with aiohttp.ClientSession() as session:
            for player_input in player_inputs:
                accounts, name, role = [], None, None
                
                if '#' in player_input:
                    riot_id, tag_line = player_input.split('#', 1)
                    self.log_message(f"--- Szukam gracza po Riot ID: {player_input} ---")
                    found_accounts = await get_puuid_by_riot_id(session, riot_id, tag_line)
                    if found_accounts:
                        accounts, name, role = found_accounts, player_input, None
                else:
                    self.log_message(f"--- Szukam pro-gracza: {player_input} ---")
                    player_data, original_name = self.find_pro_player_data(player_input)
                    if player_data:
                        accounts, name, role = player_data.get("accounts", []), original_name, player_data.get("role", "UNKNOWN")
                
                if not accounts:
                    self.log_message(f"BŁĄD: Nie znaleziono gracza '{player_input}'.\n")
                    continue

                champion_counts = await self.analyze_player(session, name, role, accounts, current_patch)
                if champion_counts:
                    combined_champion_counts.update(champion_counts)
            
            if len(player_inputs) > 1:
                self.log_message("\n=============================================")
                self.log_message("--- ŁĄCZNE PODSUMOWANIE (WSZYSCY GRACZE) ---")
                self.log_message("=============================================")
                if not combined_champion_counts:
                    self.log_message("Brak danych do stworzenia podsumowania.")
                else:
                    limit = 3 if self.top3_checkbox_var.get() == 1 else None
                    for champion, count in combined_champion_counts.most_common(limit):
                        self.log_message(f"   - {champion}: {count} gier")

        self.analyze_button.configure(state="normal", text="Analizuj")
    
    async def analyze_player(self, session, name, role, accounts, current_patch):
        if role: role = role.upper()
        if role == "ADC": role = "BOTTOM"
        role_info = f" | Rola: {role}" if role else ""
        self.log_message(f"Znaleziono: {name}{role_info} | Konta: {len(accounts)}")
        if not accounts: return None

        all_champions_played = []
        
        for puuid, server in accounts:
            match_ids = await get_match_ids(session, puuid, server)
            if match_ids:
                
                games_on_patch_and_role = 0
                for match_id in match_ids:
                    match_data = await get_match_details(session, match_id, server)
                    if not match_data: continue
                    
                    match_patch = ".".join(match_data['info']['gameVersion'].split('.')[:2])
                    
                    if match_patch == current_patch:
                        if match_data['info']['queueId'] in DESIRED_QUEUE_IDS:
                            for p in match_data['info']['participants']:
                                if p['puuid'] == puuid:
                                    participant_role = p.get('individualPosition', 'NONE').upper()
                                    if participant_role == 'UTILITY': participant_role = 'SUPPORT'
                                    
                                    # === POPRAWKA LOGIKI JEST TUTAJ ===
                                    if role is None or participant_role == role:
                                        all_champions_played.append(p['championName'])
                                        games_on_patch_and_role += 1
                                    break 
                    else:
                        break 
                
                if games_on_patch_and_role > 0:
                     self.log_message(f"   -> Znaleziono {games_on_patch_and_role} gier (na właściwej roli) na patchu {current_patch} na koncie w regionie {server.capitalize()}.")
        
        if not all_champions_played:
            self.log_message(f"Nie znaleziono gier na patchu {current_patch} dla {name}.\n")
            return None
        else:
            champion_counts = Counter(all_champions_played)
            self.log_message(f"Postacie, którymi {name} grał na patchu {current_patch}:")
            limit = 3 if self.top3_checkbox_var.get() == 1 else None
            for champion, count in champion_counts.most_common(limit):
                self.log_message(f"   - {champion}: {count} gier")
            self.log_message("")
            return champion_counts

if __name__ == "__main__":
    app = App()
    app.mainloop()