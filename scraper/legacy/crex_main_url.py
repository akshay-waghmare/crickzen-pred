import logging
from flask import Flask, jsonify , request
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import requests
import cricket_data_service
import threading
import time
import sqlite3
from crex_scraper import fetchData
from shared import scraping_tasks

app = Flask(__name__)
CORS(app, resources={
    r"/add-lead": {
        "origins": "*",  # Allow all origins for testing
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Configure logging
logging.basicConfig(filename='crex_scraper.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class ScrapeError(Exception):
    pass

class NetworkError(ScrapeError):
    pass

class DOMChangeError(ScrapeError):
    pass

DB_FILE = 'url_state.db'

def initialize_database():
    """Creates database and tables if they don't exist."""
    logging.info("Initializing database")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_urls (
                url TEXT PRIMARY KEY,
                deletion_attempts INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('DELETE FROM scraped_urls')
        
        # Add leads table creation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website TEXT,
                contact_email TEXT,
                phone_number TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logging.info("All URLs removed from the table")
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
    finally:
        conn.close()

def store_urls(urls):
    logging.info(f"Storing URLs: {urls}")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executemany("INSERT INTO scraped_urls (url, deletion_attempts) VALUES (?, 0) ON CONFLICT(url) DO UPDATE SET deletion_attempts = 0", [(url,) for url in urls])
        conn.commit()
        logging.info("URLs stored successfully")
    except Exception as e:
        logging.error(f"Error storing URLs: {e}")
    finally:
        conn.close()
    

def load_previous_urls():
    logging.info("Loading previous URLs")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM scraped_urls")
        results = cursor.fetchall()
        logging.info(f"Previous URLs loaded: {results}")
        return [row[0] for row in results]
    except Exception as e:
        logging.error(f"Error loading previous URLs: {e}")
        return []
    finally:
        conn.close()

def get_changes(new_urls):
    logging.info(f"Calculating changes for new URLs: {new_urls}")
    previous_urls = load_previous_urls()
    added_urls = set(new_urls) - set(previous_urls)
    deleted_urls = set(previous_urls) - set(new_urls)
    logging.info(f"Added URLs: {added_urls}, Deleted URLs: {deleted_urls}")
    return added_urls, deleted_urls

def job():
    logging.info("Starting job")
    url = "https://crex.live"
    with sync_playwright() as p:
            browser = p.chromium.launch(
            # user_data_dir="/tmp/playwright",  # Persistent context to reuse resources
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']  # Reduce resource usage
            )
            #context = browser.new_context()
            page = browser.new_page()

            while True:
                try:
                    url = "https://crex.live"
                    scrape(page, url)
                    time.sleep(60)
                except Exception as e:
                    logging.error(f"Error in periodic task: {e}")
                    
def scrape(page , url):
    logging.info(f"Scraping URL: {url}")
    try:
        page.goto(url)
        # wait for 10 seconds before clicking on the button
        page.wait_for_timeout(10000)
        
        # DOM Change Detection
        if not page.query_selector("div.live-card"):  
            raise DOMChangeError("Cannot locate essential 'div.live-card' element")
        
        # Evaluate JavaScript on the page to get all div.live elements and print them out
        live_divs = page.query_selector_all("div.live-card .live")

        urls = []
        for live_div in live_divs:
            # Get the parent of live_div using querySelector and then get the parent of the parent
            parent_element = live_div.query_selector(":scope >> xpath=..")
            grandparent_element = parent_element.query_selector(":scope >> xpath=..")
            sibling_element = grandparent_element.query_selector(":scope >> xpath=following-sibling::*[1]")
            url = sibling_element.get_attribute('href')
            urls.append(url)

        logging.info(f"Scraped URLs: {urls}")

        for url in urls:
            # Prepend 'https://crex.live' to the URL
            url = 'https://crex.live' + url
        # Find changes - first, before updating state 
        previous_urls = load_previous_urls()
        added_urls, deleted_urls = get_changes(urls)    
        # Treat all as added on the first run 
        if not previous_urls:   # Check if there were no previous URLs
            added_urls = urls
            deleted_urls = []
        # Now, update the database state    
        store_urls(urls)
        
        token = cricket_data_service.get_bearer_token()        
        cricket_data_service.add_live_matches(urls, token)
        
        if added_urls or deleted_urls:
            # Send the URLs to your Spring Boot app
            # fetch the bearer token from cricket-data-service
            # start scraping if url is added 
                # Start scraping if url is added
                
                
                if added_urls:
                    logging.info(f"Added URLs detected: {added_urls}")
                    """ token = cricket_data_service.get_bearer_token()
                    cricket_data_service.add_live_matches(urls, token) """
                    
                    for url in added_urls:
                        # append https://crex.live to the url
                        url = 'https://crex.live' + url
                        response = requests.post('http://127.0.0.1:5000/start-scrape', json={'url': url})
                    if response.status_code == 200:
                        logging.info(f"Scraping started for url from scrape function: {url}")
                    else:
                        logging.error(f"Failed to start scraping for url: {url}")
                        # try scraping for other urls if one fails
                
                """ if deleted_urls:
                    for url in deleted_urls:
                        url = 'https://crex.live' + url
                        response = requests.post('http://127.0.0.1:5000/stop-scrape', json={'url': url})
                    if response.status_code == 200:
                        logging.info(f"Scraping stopped for url from scrape function: {url}")
                    else:
                        logging.error(f"Failed to stop scraping for url: {url}") """
                # if deleted url check for these urls are deleted 3 times by maintaining count in the next loops
                               
        time.sleep(60)                
        # Consider updating to reflect actual scraping state
        return {'status': 'Scraping finished', 'match_urls': urls}
    except NetworkError as ne:
        logging.error(f"Network error occurred: {ne}")
        raise ne
    except DOMChangeError as de:
        logging.error(f"DOM change error occurred: {de}")
        raise de
    except Exception as e:
        logging.error(f"Error during navigation: {e}")
        raise ScrapeError(f"Error during navigation: {e}")


@app.route('/scrape-live-matches-link', methods=['GET'])
def scrape_live_matches():
    try:
        logging.info("Received request to scrape live matches")
        # Background scraping thread to prevent API blocking
        scraping_thread = threading.Thread(target=job)
        scraping_thread.daemon = True  # Mark as daemon thread
        scraping_thread.start()

        return jsonify({'status': 'Scraping started'})
    except ScrapeError as se:
        logging.error(f"Scraping error occurred: {se}")
        return jsonify({'status': 'Scraping error', 'error_message': str(se)})
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({'status': 'Error occurred', 'error_message': str(e)})

@app.route('/start-scrape', methods=['POST'])
def start_scrape():

    url = request.json.get('url')
    if url:
        logging.info(f"Received request to start scraping for URL: {url}")
        thread = threading.Thread(target=fetchData, args=(url,))
        scraping_tasks[url] = {'thread': thread, 'status': 'running'}
        thread.start()  # Start the thread
        logging.info(f"Scraping started for url: {url}")
        response = jsonify({'status': 'Scraping started for url: ' + url})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    else:
        response = jsonify({'status': 'No url provided'}), 400
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    
@app.route('/stop-scrape', methods=['POST'])
def stop_scrape():
    url = request.json.get('url')
    if url:
        logging.info(f"Received request to stop scraping for URL: {url}")
        if url in scraping_tasks:
            task_data = scraping_tasks.get(url)
            if task_data:
                logging.info(f"Stopping scraping for url: {url}")
                task_data['status'] = 'stopping'  # Signal the thread to stop
                thread = task_data['thread']
                thread.join(timeout=10)  # Add a timeout (in seconds)
                if thread.is_alive():
                    logging.warning("Thread is still alive after timeout, may need further investigation check again after some time.")                    
                else:
                    logging.info(f"Scraping stopped for url: {url}")
                    
                scraping_tasks.pop(url)
                #delete url from scraped_urls table
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM scraped_urls WHERE url=?", (url,))

                return jsonify({'status': f'Stopped scraping for url: {url}'})
            else:
                return jsonify({'status': 'No scraping task found for url: ' + url}), 400
        else:
            return jsonify({'status': 'No scraping task found for url: ' + url}), 400
    else:
        return jsonify({'status': 'No url provided'}), 400

@app.route("/add-lead", methods=["POST", "OPTIONS"])
def add_lead():
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        response = jsonify({"message": "OK"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        data = request.json
        company_name = data.get("company_name")
        website = data.get("website")
        contact_email = data.get("contact_email", "")
        phone_number = data.get("phone_number", "")
        notes = data.get("notes", "")

        if not company_name or not website:
            return jsonify({"error": "Company name and website are required"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads (company_name, website, contact_email, phone_number, notes) 
            VALUES (?, ?, ?, ?, ?)""",
            (company_name, website, contact_email, phone_number, notes))
        conn.commit()
        lead_id = cursor.lastrowid
        conn.close()

        logging.info(f"New lead added: {company_name}")
        response = jsonify({"message": "Lead added successfully", "lead_id": lead_id})
        return response, 201

    except Exception as e:
        logging.error(f"Error adding lead: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/view-leads", methods=["GET"])
def view_leads():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, company_name, website, contact_email, phone_number, notes, created_at 
            FROM leads 
            ORDER BY created_at DESC""")
        leads = cursor.fetchall()
        conn.close()

        lead_list = []
        for lead in leads:
            lead_list.append({
                "id": lead[0],
                "company_name": lead[1],
                "website": lead[2],
                "contact_email": lead[3],
                "phone_number": lead[4],
                "notes": lead[5],
                "created_at": lead[6]
            })

        return jsonify({"leads": lead_list}), 200

    except Exception as e:
        logging.error(f"Error fetching leads: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/update-lead/<int:lead_id>", methods=["PUT"])
def update_lead(lead_id):
    try:
        data = request.json
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if lead exists
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Lead not found"}), 404

        # Update lead
        update_fields = []
        values = []
        for field in ["company_name", "website", "contact_email", "phone_number", "notes"]:
            if field in data:
                update_fields.append(f"{field} = ?")
                values.append(data[field])
        
        if update_fields:
            values.append(lead_id)
            query = f"UPDATE leads SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            
        conn.close()
        logging.info(f"Lead {lead_id} updated successfully")
        return jsonify({"message": "Lead updated successfully"}), 200

    except Exception as e:
        logging.error(f"Error updating lead: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/delete-lead/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if lead exists
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Lead not found"}), 404

        # Delete lead
        cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()
        
        logging.info(f"Lead {lead_id} deleted successfully")
        return jsonify({"message": "Lead deleted successfully"}), 200

    except Exception as e:
        logging.error(f"Error deleting lead: {e}")
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port=5000, debug=True)
