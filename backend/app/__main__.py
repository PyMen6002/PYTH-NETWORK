from backend.app import app, PORT
from backend.util.log import log_info


if __name__ == "__main__":
    log_info(f"[HTTP] Flask server starting on port {PORT}")
    app.run(port=PORT)
