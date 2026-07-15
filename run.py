"""Entry point for the FOI Deadline Tracker."""
import os

from foi_tracker.app import app

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(debug=debug, port=5002)
