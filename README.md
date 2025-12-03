# Pro-Stats Tracker & Analyzer

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-green)
![Status](https://img.shields.io/badge/Status-Active-success)

**Pro-Stats Tracker** is a desktop application designed for League of Legends analysts and enthusiasts. It aggregates and analyzes match data from professional players across multiple regions (LCK, LPL, etc.) to identify meta trends and champion pools in real-time.

Unlike standard trackers, this tool features a custom-built caching system and an OSINT-based data collection module.

## 🚀 Key Features

* **Async Data Fetching:** Utilizes `aiohttp` and `asyncio` for high-performance, non-blocking API calls to Riot Games servers across different routing regions (Asia, Europe, Americas).
* **Smart Caching (SQL):** Implements a local SQLite database (`match_cache.db`) to store match details. This drastically reduces API usage limits and speeds up repeated queries by 90%.
* **OSINT Generator:** Includes a separate module (`generator.py`) that performs reverse-engineering on public tracking sites using Selenium to automatically discover and verify pro players' hidden soloQ accounts.
* **Security-First approach:** Implements parameterized SQL queries to prevent injection vulnerabilities and separates configuration logic.

## 🛠️ Architecture

The project consists of two main modules:

1.  **Tracker (GUI):** Built with `customtkinter`. It handles user input, communicates with the Riot API via a rotating region check, and visualizes the data.
2.  **Generator (Scraper):** A tool for maintaining the `players.json` database. It uses `undetected_chromedriver` to bypass bot protection on tracking websites.

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/haski139/lolstats.git
    cd lolstats
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: Key libraries include `customtkinter`, `aiohttp`, `requests`, `undetected_chromedriver`)*

3.  **Configuration:**
    * Create a `config.py` file in the root directory.
    * Add your Riot Games API Key:
        ```python
        API_KEY = "RGAPI-YOUR-KEY-HERE"
        ```

## 🎮 Usage

### Running the Tracker
```bash
python prostatstracker.py
```

* Enter a player's name (e.g., "Faker", "Caps") or a specific Riot ID.

* The tool will scan known accounts, filter matches by the current patch, and display champion statistics.

### Updating the Database (Advanced)
If you want to regenerate the `players.json` file:

1. Open `generator.py`.

2. Ensure you have Google Chrome installed (or configure the `browser_path` variable manually if using Brave/Edge).

3. Run:

Bash

```bash
python generator.py
```

## 🛡️ Security & Privacy
* **API Key Safety:** The config.py file is included in .gitignore to prevent accidental leakage of secrets.

* **Data Handling:** All data is processed locally. The application queries official Riot APIs and public websites only.

## 📝 Disclaimer
This project is not endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.