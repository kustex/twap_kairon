# TWAP Order Execution Dashboard

This project is a **TWAP (Time-Weighted Average Price)** trading engine with a built-in **Dash web dashboard** for scheduling and monitoring trades across crypto exchanges (e.g., Bybit, Binance, Bitget).

---

## 🚀 Features

- 🧠 Multi-threaded TWAP execution using background workers
- 🗓️ Schedule jobs with custom trade size, delay, and price limits
- 🔐 Encrypted API key storage using Fernet (AES-128)
- 📊 Real-time Dash dashboard with:
  - Add Exchange panel
  - Submitted Trades table
  - Scheduled Jobs table
  - Active Jobs monitor
- 💾 Uses SQLite for persistent logging of jobs and executions

---

## 🧱 Tech Stack

- `Dash`, `dash-bootstrap-components` — frontend UI
- `ccxt` — exchange integration
- `cryptography` — credential encryption
- `sqlite3` — lightweight DB storage
- `threading`, `queue` — job execution engine

---

## 🛠️ Usage

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
python app_dash.py
```

### 3. Open your browser
Go to `http://127.0.0.1:8050/`

### 4. Add an exchange
Fill in your API key/secret (and optional password), then click "Save Exchange".

---

## 📁 Project Structure
```
├── app_dash.py                # Main Dash app
├── twap_engine/
│   ├── __init__.py           # Launches scheduler + executor
│   ├── db.py                 # SQLite DB logging
│   ├── executor.py           # Executes orders using ccxt
│   ├── scheduler_twap.py     # Handles TWAP job scheduling
│   └── encryption_utils.py   # Fernet key + encryption helpers
├── exchanges.secure          # Encrypted exchange credentials (ignored)
├── secret.key                # Fernet encryption key (ignored)
├── twap_jobs.db              # Job/order logs (ignored)
└── README.md
```

---

## 📜 License
MIT — use freely, at your own risk!

---

## ✍️ Author
Built by Kustex
