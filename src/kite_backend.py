import time
import threading
import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect
from expressoptionchain.option_stream import OptionStream
from expressoptionchain.option_chain import OptionChainFetcher

from src.logger import setup_logger

logger = setup_logger("option_app")

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TOKEN_FILE = "access_token.txt"
EXPIRY = "25-11-2025"
STOCK_SYMBOL = "HDFCBANK"

kite = KiteConnect(api_key=API_KEY)
access_token = None
latest_chain = []

stream_thread_started = False
option_stream_instance = None
chain_updater_thread = None


# HELPERS
def get_val(data, key):
    if data is None:
        return 0
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


# THREAD CONTROL
def stop_stream_service():
    global stream_thread_started, option_stream_instance, latest_chain

    logger.info("Stopping stream service...")
    stream_thread_started = False
    latest_chain = []

    if option_stream_instance:
        logger.info("Releasing OptionStream instance")
        option_stream_instance = None

    time.sleep(0.5)
    logger.info("Stream service stopped")


def chain_updater():
    global latest_chain, stream_thread_started, STOCK_SYMBOL, EXPIRY

    logger.info("Chain updater started for %s (%s)", STOCK_SYMBOL, EXPIRY)
    fetcher = OptionChainFetcher()

    while stream_thread_started:
        try:
            data = fetcher.get_option_chain(f"NFO:{STOCK_SYMBOL}")
            expiry_data = data.get("expiry", {}).get(EXPIRY, [])
            if expiry_data:
                latest_chain = format_chain_for_strikes(expiry_data)
        except Exception:
            logger.exception("Error while updating option chain")
        time.sleep(1)

    logger.warning("Chain updater thread terminated")


def start_stream_service(token):
    global stream_thread_started, option_stream_instance, chain_updater_thread

    stop_stream_service()
    logger.info("Starting stream for %s (%s)", STOCK_SYMBOL, EXPIRY)

    secrets = {
        "api_key": API_KEY,
        "api_secret": API_SECRET,
        "access_token": token
    }

    try:
        option_stream_instance = OptionStream(
            [f"NFO:{STOCK_SYMBOL}"], secrets, expiry=EXPIRY
        )
        option_stream_instance.start(threaded=True)

        stream_thread_started = True
        chain_updater_thread = threading.Thread(
            target=chain_updater, daemon=True
        )
        chain_updater_thread.start()

    except Exception:
        logger.exception("Failed to start stream service")
        stream_thread_started = False
        option_stream_instance = None


# TOKEN HANDLING
def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    logger.info("Access token saved to file")


def get_valid_token_from_file():
    if not os.path.exists(TOKEN_FILE):
        return None

    try:
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()

        kite.set_access_token(token)
        kite.profile()

        logger.info("Token loaded and validated successfully")
        return token

    except Exception:
        logger.warning("Saved token invalid or expired, deleting file")
        try:
            os.remove(TOKEN_FILE)
        except OSError:
            pass
        return None

