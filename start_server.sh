#!/bin/bash
# Change to the project directory using a relative path
cd "$(dirname "$0")/PROJECT"
# Start the Flask app
python3 webapp/app.py "$@"
