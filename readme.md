# Zerodha Option Chain Dashboard (Flask + KiteConnect + ExpressOptionChain)

A small Flask web app that:
- Authenticates with **Zerodha Kite** (OAuth login flow)
- Stores the **access_token** locally (`access_token.txt`) and reuses it if still valid
- Starts a background **OptionStream** and a 1-second polling **option-chain updater**
- Serves a UI page (templates) and a `/data` JSON endpoint for the latest formatted option chain
- Lets you dynamically switch **stock symbol** and **expiry** via `/update_config` (POST)

> Uses `kiteconnect` + `expressoptionchain` to stream and fetch option-chain data for instruments like `NFO:HDFCBANK`.

---

## Features

- **Login via Zerodha** using `kite.login_url()`
- **Callback handler** (`/callback`) to generate session + get `access_token`
- **Token persistence** in `access_token.txt`
- **Token validation** on startup and on visiting `/` (uses `kite.profile()`)
- **Live-ish option chain updates** every 1 second via a background thread
- **JSON endpoint** for frontends to poll:
  - `GET /data` → returns `latest_chain`
- **Runtime config update**
  - `POST /update_config` with `{ "symbol": "...", "expiry": "DD-MM-YYYY" }`

---

## Project Structure

```
.
├── src/                      
├── templates/
│   ├── login.html               # login page
│   └── index.html               # dashboard page
├── .env                         # API_KEY, API_SECRET
├── requirements.txt
└── access_token.txt             # created automatically after first login
```

> If `templates/` is missing, Flask will raise a template-not-found error when you open `/`.

---

## Requirements

- Python 3.9+ (recommended)
- Zerodha Kite developer app credentials:
  - `API_KEY`
  - `API_SECRET`
- A redirect URL configured in the Zerodha developer console to match your app callback route  
  Example: `http://127.0.0.1:5000/callback`

---

## Setup

### 1) Create and activate a virtual environment

**Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

Example `requirements.txt` (adjust versions as needed):
```txt
flask
python-dotenv
kiteconnect
expressoptionchain
```

---

## Configuration

Create a `.env` file in the project root:

```env
API_KEY=your_zerodha_api_key
API_SECRET=your_zerodha_api_secret
```

In your code, these are loaded via:
- `load_dotenv()`
- `os.getenv("API_KEY")`
- `os.getenv("API_SECRET")`

---

## Running the App

Start the Flask server:

```bash
python app.py
```

By default it runs on:
- `http://127.0.0.1:5000`

### First-time login flow

1. Open `http://127.0.0.1:5000`
2. You’ll see the login page (if `access_token` is not present/valid).
3. Click login → redirects to Zerodha.
4. Approve login → Zerodha redirects back to `/callback`.
5. App saves `access_token` to `access_token.txt`.
6. Stream + updater threads start automatically.
7. You are redirected to `/`.

### Subsequent runs

- If `access_token.txt` exists, the app validates it using `kite.profile()`.
- If valid → it skips login and starts stream immediately.
- If invalid/expired → it deletes the file and asks you to login again.

---

## Endpoints

### `GET /`
- If token is valid → renders `index.html`
- Else → renders `login.html`

### `GET /login`
Redirects to Zerodha login URL.

### `GET /callback`
Handles Zerodha redirect and exchanges `request_token` for `access_token`.

### `GET /data`
Returns the latest formatted option chain:
- Returns `[]` if not logged in
- Otherwise returns a list of strike rows like:

```json
[
  {
    "strike": 1600,
    "ce_oi": 12345,
    "ce_chg_oi": 100,
    "ce_volume": 234,
    "ce_iv": 12.3,
    "ce_ltp": 10.5,
    "ce_chg": -0.2,
    "ce_bid_qty": 50,
    "ce_bid": 10.4,
    "ce_ask": 10.6,
    "ce_ask_qty": 45,
    "pe_bid_qty": 40,
    "pe_bid": 9.9,
    "pe_ask": 10.1,
    "pe_ask_qty": 42,
    "pe_chg": 0.1,
    "pe_ltp": 10.0,
    "pe_iv": 13.1,
    "pe_volume": 210,
    "pe_chg_oi": -20,
    "pe_oi": 11000
  }
]
```

### `POST /update_config`
Updates the running symbol + expiry and restarts the stream.

**Request body:**
```json
{
  "symbol": "HDFCBANK",
  "expiry": "25-11-2025"
}
```

**Response:**
```json
{ "status": "success", "message": "Stream updated successfully." }
```

---

## Default Runtime Parameters

In the code:
- `STOCK_SYMBOL = "HDFCBANK"`
- `EXPIRY = "25-11-2025"`
- `TOKEN_FILE = "access_token.txt"`

The option-chain fetcher uses:
- `fetcher.get_option_chain(f"NFO:{STOCK_SYMBOL}")`

---

## Notes / Common Issues

### 1) Expiry format must match provider response
`EXPIRY` must exactly match the expiry key used under:
```python
data.get("expiry", {}).get(EXPIRY, [])
```
If the expiry string doesn’t match, you’ll keep getting an empty chain.

### 2) Zerodha redirect URL mismatch
If your Zerodha app redirect URL doesn’t match `http://127.0.0.1:5000/callback`,
login will fail or you won’t get a `request_token`.

### 3) Debug mode auto-reloader
Flask `debug=True` can run your app twice due to the reloader, which may cause threads to start twice.
If you observe duplicate logs, run with `debug=False` or use:
```bash
python -m flask run --no-reload
```

---

## Security Warning

- `access_token.txt` is sensitive. Treat it like a password.
- Add it to `.gitignore`:

```gitignore
.env
access_token.txt
__pycache__/
.venv/
```

---
