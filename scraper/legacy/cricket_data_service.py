import requests
import json
import requests
import json
import os
import logging 

logging.basicConfig(filename='crex_scraper.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_bearer_token():
    # Define the URL of the token endpoint
    token_url = os.getenv('TOKEN_URL', 'http://127.0.0.1:8099/token/generate-token')


    # Define the credentials required to obtain the token (if needed)
    credentials = {
    "username": "tanmay",
    "password": "tanmay"
    }

    try:
        logging.info("Requesting bearer token from token endpoint.")
        # Send a POST request to the token endpoint to obtain the token
        response = requests.post(token_url, json=credentials)

        # Check the response status code
        if response.status_code == 200:
            # Parse the JSON response to get the token
            token_data = response.json()
            logging.info("Bearer token obtained successfully.")
            return token_data.get("token")
        else:
            logging.error(f"Failed to obtain bearer token. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while obtaining bearer token: {str(e)}")



def send_cricket_data_to_service(data, bearer_token,url):
    # Define the URL of the service where you want to send the data
    service_url = os.getenv('SERVICE_URL', 'http://127.0.0.1:8099/cricket-data')

    # NOTE: /cricket-data endpoint is PUBLIC (permitAll in WebSecurityConfig)
    # No authentication required, but we still accept token for backwards compatibility
    headers = {
        "Content-Type": "application/json"
    }
    
    # Add token only if provided (not required since endpoint is public)
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    # Convert the data to JSON (assuming data is a dictionary)
    #json_data = json.dumps(data)
    json_payload = {}
    try:
        logging.info("Preparing data to send to the service.")
        #filter data before sending  only non None values are sent
        if isinstance(data, list) :
            filtered_data = [
            {k: v for k, v in item.items() if v is not None} for item in data
        ]
            json_payload = {"data": filtered_data, "url": url}
            print("json_payload to be sent back for test match " , json_payload)
        else : 
            filtered_data = {k: v for k, v in data.items() if v is not None}
            filtered_data['url'] = url
            json_payload = filtered_data
            
            
        logging.info(f"Sending data to service URL: {service_url}")
        logging.debug(f"Payload: {json_payload}")
        
        # Send the POST request to the service (works even without token!)
        response = requests.post(service_url, headers=headers, json=json_payload)

        # Check the response status code
        if response.status_code == 200:
            logging.info("Data sent successfully to the service.")
        else:
            logging.error(f"Failed to send data. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while sending data: {str(e)}")
        
        
def add_live_matches(data, bearer_token):
    # Define the URL of the service where you want to send the data
    service_url = os.getenv('ADD_LIVE_MATCHES_URL', 'http://127.0.0.1:8099/cricket-data/add-live-matches')
    
    # Define the headers with the bearer token
    headers = {
        "Content-Type": "application/json"
    }
    
    # Add Authorization header only if token is provided
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    try:
        # Convert the data to a JSON array
        payload = json.dumps(data)
        logging.info(f"Payload: {payload}")
        # Send the POST request to the service
        response = requests.post(service_url, headers=headers, data=payload)

        # Check the response status code
        if response.status_code == 200:
            logging.info("Live matches data added successfully.")
        else:
             logging.error(f"Failed to add live matches data. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while adding live matches data: {str(e)}")

def send_data_to_api_endpoint(data, bearer_token, url, api_endpoint=None):
    if api_endpoint is None:
        api_endpoint = os.getenv('API_ENDPOINT', 'http://127.0.0.1:8099/cricket-data/match-info/save')

    headers = {
        "Content-Type": "application/json"
    }
    
    # Add Authorization header only if token is provided
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    try:
        logging.info("Preparing data to send to the API endpoint.")

        if isinstance(data, dict):
            json_payload = data.copy()
            json_payload['url'] = url
        else:
            logging.error("Data should be a dictionary.")
            return False

        # Serialize the payload to JSON string
        try:
            json_payload_str = json.dumps(json_payload)
            logging.debug(f"Serialized JSON payload: {json_payload_str}")
        except Exception as e:
            logging.error(f"Error serializing json_payload: {e}")
            return False

        logging.info(f"Sending data to API endpoint: {api_endpoint}")

        # Send the POST request with the JSON string
        response = requests.post(api_endpoint, headers=headers, data=json_payload_str, timeout=5)

        if 200 <= response.status_code < 300:
            logging.info("Data sent successfully to the API endpoint.")
            return True
        else:
            logging.error(f"Failed to send data. Status code: {response.status_code}")
            logging.error(f"Response content: {response.text}")
            return False
    except Exception as e:
        logging.exception(f"An error occurred while sending data: {str(e)}")
        return False
                        

        

        

