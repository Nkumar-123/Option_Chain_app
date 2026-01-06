from flask import jsonify, render_template, request, redirect, url_for

from src.kite_backend import (
    kite,
    API_SECRET,
    start_stream_service,
    save_token,
    get_valid_token_from_file,
)
import src.kite_backend as backend


def register_routes(app):

    @app.route("/")
    def home():
        if not backend.access_token:
            valid_token = get_valid_token_from_file()
            if valid_token:
                backend.access_token = valid_token
                start_stream_service(backend.access_token)

        if backend.access_token:
            return render_template(
                "index.html",
                stock_name=backend.STOCK_SYMBOL,
                expiry=backend.EXPIRY,
            )

        return render_template("login.html")

    @app.route("/login")
    def login():
        return redirect(kite.login_url())

    @app.route("/callback")
    def callback():
        request_token = request.args.get("request_token")

        if not request_token:
            logger.error("Callback received without request token")
            return "Error: No token."

        try:
            data = kite.generate_session(
                request_token, api_secret=API_SECRET
            )
            backend.access_token = data["access_token"]
            save_token(backend.access_token)

            kite.set_access_token(backend.access_token)
            start_stream_service(backend.access_token)

            return redirect(url_for("home"))

        except Exception:
            logger.exception("Login callback failed")
            return "Login failed"

    @app.route("/data")
    def data():
        if not backend.access_token:
            return jsonify([])
        return jsonify(backend.latest_chain)

    @app.route("/update_config", methods=["POST"])
    def update_config():
        payload = request.get_json()
        new_symbol = payload.get("symbol", "").upper()
        new_expiry = payload.get("expiry")

        if new_symbol and new_expiry and backend.access_token:
            backend.STOCK_SYMBOL = new_symbol
            backend.EXPIRY = new_expiry
            start_stream_service(backend.access_token)

            return jsonify(
                {"status": "success", "message": "Stream updated successfully."}
            )
        logger.warning("Invalid update request received")
        return jsonify(
            {"status": "error", "message": "Invalid configuration"}
        ), 400

