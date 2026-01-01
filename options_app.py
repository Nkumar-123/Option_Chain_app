import time
import threading
import os
import config
from flask import Flask, jsonify, render_template, request, redirect, url_for
from kiteconnect import KiteConnect
from expressoptionchain.option_stream import OptionStream
from expressoptionchain.option_chain import OptionChainFetcher

app = Flask(__name__)

# --- CONFIG ---
API_KEY = config.API_KEY     
API_SECRET = config.API_SECRET
EXPIRY = "25-11-2025"
STOCK_SYMBOL = "HDFCBANK"           
TOKEN_FILE = "access_token.txt"     

kite = KiteConnect(api_key=API_KEY)
access_token = None
latest_chain = []
stream_thread_started = False
# References for active threads
option_stream_instance = None
chain_updater_thread = None

# --- DATA HELPERS ---
def get_val(data, key):
    if data is None: return 0
    if isinstance(data, list):
        return data[0].get(key, 0) if len(data) > 0 else 0
    if isinstance(data, dict):
        return data.get(key, 0)
    return data

def format_chain_for_strikes(expiry_data):
    formatted_chain = []
    for s in expiry_data:
        strike = s.get("strike_price")
        ce = s.get("ce", {})
        pe = s.get("pe", {})

        formatted_chain.append({
            "strike": strike,
            "ce_oi": get_val(ce.get("oi"), "oi"),
            "ce_chg_oi": get_val(ce.get("oi_change"), "oi"),
            "ce_volume": get_val(ce.get("volume"), "volume"),
            "ce_iv": get_val(ce.get("iv"), "iv"),
            "ce_ltp": get_val(ce.get("premium"), "price"),
            "ce_chg": get_val(ce.get("change"), "change"),
            "ce_bid_qty": get_val(ce.get("bid"), "quantity"),
            "ce_bid": get_val(ce.get("bid"), "price"),
            "ce_ask": get_val(ce.get("ask"), "price"),
            "ce_ask_qty": get_val(ce.get("ask"), "quantity"),
            "pe_bid_qty": get_val(pe.get("bid"), "quantity"),
            "pe_bid": get_val(pe.get("bid"), "price"),
            "pe_ask": get_val(pe.get("ask"), "price"),
            "pe_ask_qty": get_val(pe.get("ask"), "quantity"),
            "pe_chg": get_val(pe.get("change"), "change"),
            "pe_ltp": get_val(pe.get("premium"), "price"),
            "pe_iv": get_val(pe.get("iv"), "iv"),
            "pe_volume": get_val(pe.get("volume"), "volume"),
            "pe_chg_oi": get_val(pe.get("oi_change"), "oi"),
            "pe_oi": get_val(pe.get("oi"), "oi"),
        })
    return formatted_chain

# --- THREAD CONTROL ---

def stop_stream_service():
    """Stops existing stream and updater threads gracefully."""
    global stream_thread_started, option_stream_instance, latest_chain
    
    # stop updater thread
    stream_thread_started = False
    latest_chain = []
    if option_stream_instance:
        print(">>> Attempting to release OptionStream instance...")
        option_stream_instance = None        
    time.sleep(0.5) 
    print(">>> Stream service stopped.")

def chain_updater():
    """
    Background task to fetch option chain data, controlled by a flag.
    """
    global latest_chain, stream_thread_started, STOCK_SYMBOL, EXPIRY
    print(f">>> Chain Updater Active for {STOCK_SYMBOL} ({EXPIRY})")
    
    fetcher = OptionChainFetcher()
    
    while stream_thread_started:
        try:
            data = fetcher.get_option_chain(f"NFO:{STOCK_SYMBOL}")
            expiry_data = data.get("expiry", {}).get(EXPIRY, [])
            if expiry_data:
                latest_chain = format_chain_for_strikes(expiry_data)
        except Exception as e:
            print(f"Updater Error: {e}")
        time.sleep(1)
    print(">>> Chain Updater thread terminated.")


def start_stream_service(token):
    """Stops existing stream and restart the service with current global values."""
    
    global stream_thread_started, option_stream_instance, chain_updater_thread, STOCK_SYMBOL, EXPIRY
    
    stop_stream_service()
    
    print(f">>> Starting Stream for {STOCK_SYMBOL} ({EXPIRY})...")
    
    secrets = {
        "api_key": API_KEY,
        "api_secret": API_SECRET,
        "access_token": token
    }

    try:
        option_stream_instance = OptionStream([f"NFO:{STOCK_SYMBOL}"], secrets, expiry=EXPIRY)
        option_stream_instance.start(threaded=True)
        
        # Start Chain Updater
        stream_thread_started = True
        chain_updater_thread = threading.Thread(target=chain_updater, daemon=True)
        chain_updater_thread.start()
        
    except Exception as e:
        print(f"Stream Start Error: {e}")
        stream_thread_started = False
        option_stream_instance = None

# --- FILE VALIDATION ---
def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

def get_valid_token_from_file():
    """
    Reads token from file, checks with Zerodha if it's still valid.
    If invalid: Deletes the file and returns None.
    If valid: Returns the token string.
    """
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
            
            # Temporarily set token to check validity
            kite.set_access_token(token)
            
            # Attempt a API call to validate session
            kite.profile()
            
            print(">>> Token loaded from file and successfully validated.")
            return token
            
        except Exception as e:
            print(f">>> Found saved token, but it is invalid/expired: {e}")
            print(">>> Deleting invalid access_token file...")
            try:
                os.remove(TOKEN_FILE)
            except OSError:
                pass 
            return None
    return None

@app.route("/")
def home():
    global access_token
    
    # Check memory first
    if not access_token:
        valid_token = get_valid_token_from_file()
        if valid_token:
            access_token = valid_token
            start_stream_service(access_token) 
    if access_token:
        return render_template("index.html", stock_name=STOCK_SYMBOL, expiry=EXPIRY)
    
    # Login Page (shown if access_token is None)
    return '''
        <div style="display:flex; flex-direction:column; height:100vh; justify-content:center; align-items:center; font-family:sans-serif; background:#f4f4f4;">
            <h2>Option Chain Login</h2>
            <a href="/login" style="padding:15px 30px; background:#ff5722; color:white; text-decoration:none; border-radius:5px; font-size:18px; font-weight:bold;">
                Login with Zerodha
            </a>
        </div>
    '''

@app.route("/login")
def login():
    return redirect(kite.login_url())

@app.route("/callback")
def callback():
    global access_token
    request_token = request.args.get("request_token")
    if not request_token: return "Error: No token."

    try:
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = data["access_token"]
        save_token(access_token)
        
        kite.set_access_token(access_token)
        start_stream_service(access_token)
        return redirect(url_for('home'))
    except Exception as e:
        return f"Error: {e}"

@app.route("/data")
def data():
    if not access_token: return jsonify([])
    return jsonify(latest_chain)

@app.route("/update_config", methods=['POST'])
def update_config():
    global STOCK_SYMBOL, EXPIRY, access_token
    
    data = request.get_json()
    new_symbol = data.get('symbol').upper()
    new_expiry = data.get('expiry')
    
    if new_symbol and new_expiry and access_token:
        print(f">>> User requested update: {new_symbol} / {new_expiry}")
        
        STOCK_SYMBOL = new_symbol
        EXPIRY = new_expiry
        
        start_stream_service(access_token) 
        
        return jsonify({"status": "success", "message": "Stream updated successfully."})
    
    return jsonify({"status": "error", "message": "Invalid configuration or no access token."}), 400


if __name__ == "__main__":
    # Startup Check: Validate token
    valid_token = get_valid_token_from_file()
    
    if valid_token:
        access_token = valid_token
        # Token is valid
        start_stream_service(access_token) 
    else:
        print(">>> No valid saved token found. Waiting for user login.")

    app.run(debug=True, port=5000)
