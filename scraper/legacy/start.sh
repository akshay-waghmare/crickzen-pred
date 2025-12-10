#!/bin/bash
set -x

# Start the Flask application
python /app/crex_main_url.py &

# Wait for the Flask app to start
sleep 65

# Make the GET request to start the scraping process
curl http://127.0.0.1:5000/scrape-live-matches-link

# Keep the container running
tail -f /app/crex_scraper.log