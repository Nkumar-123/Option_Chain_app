from flask import Flask
import os

from src.kite_backend import (
    get_valid_token_from_file,
    start_stream_service,
)
import src.kite_backend as backend
from src.routes import register_routes

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
)

register_routes(app)

if __name__ == "__main__":
    valid_token = get_valid_token_from_file()

    if valid_token:
        backend.access_token = valid_token
        start_stream_service(backend.access_token)

    app.run(debug=True, port=5000)

