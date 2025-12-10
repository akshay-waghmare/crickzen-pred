"""
Batched Cricket Data Service - Performance Optimization

This module provides batched API calls to reduce network overhead.
Instead of sending individual requests every 2.5 seconds, we batch
multiple updates and send them together.
"""
import requests
import json
import os
import logging
import threading
import time
from collections import defaultdict
from typing import Dict, List, Any, Optional

logging.basicConfig(filename='crex_scraper.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class BatchedCricketDataService:
    """
    Batches cricket data updates to reduce API call frequency.
    
    Features:
    - Accumulates updates for each URL
    - Flushes batch after max_batch_size updates or flush_interval seconds
    - Thread-safe operation
    - Automatic background flushing
    """
    
    def __init__(
        self,
        max_batch_size: int = 10,
        flush_interval: float = 5.0,
        service_url: Optional[str] = None
    ):
        self.max_batch_size = max_batch_size
        self.flush_interval = flush_interval
        self.service_url = service_url or os.getenv('SERVICE_URL', 'http://127.0.0.1:8099/cricket-data')
        
        # Batch storage: url -> list of data items
        self._batches: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_flush_time: Dict[str, float] = {}
        self._flush_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._bearer_token: Optional[str] = None
        
        # Start background flusher
        self._start_background_flusher()
    
    def set_bearer_token(self, token: Optional[str]) -> None:
        """Set the bearer token for API authentication."""
        self._bearer_token = token
    
    def queue_update(self, data: Any, url: str) -> None:
        """
        Queue a cricket data update for batching.
        
        Args:
            data: The data to send (dict or list)
            url: The match URL
        """
        with self._lock:
            # Filter None values
            if isinstance(data, list):
                filtered_data = [
                    {k: v for k, v in item.items() if v is not None} 
                    for item in data
                ]
            elif isinstance(data, dict):
                filtered_data = {k: v for k, v in data.items() if v is not None}
            else:
                logging.error(f"Invalid data type for batching: {type(data)}")
                return
            
            self._batches[url].append(filtered_data)
            
            # Initialize last flush time for new URLs
            if url not in self._last_flush_time:
                self._last_flush_time[url] = time.time()
            
            # Check if we should flush this batch
            batch_size = len(self._batches[url])
            time_since_flush = time.time() - self._last_flush_time[url]
            
            if batch_size >= self.max_batch_size or time_since_flush >= self.flush_interval:
                self._flush_batch_locked(url)
    
    def _flush_batch_locked(self, url: str) -> None:
        """Flush a batch for a specific URL (must be called with lock held)."""
        if not self._batches[url]:
            return
        
        batch_data = self._batches[url]
        self._batches[url] = []
        self._last_flush_time[url] = time.time()
        
        # Release lock before making network call
        self._lock.release()
        try:
            self._send_batched_data(batch_data, url)
        finally:
            self._lock.acquire()
    
    def _send_batched_data(self, batch_data: List[Dict[str, Any]], url: str) -> None:
        """Send a batch of data to the backend."""
        headers = {"Content-Type": "application/json"}
        
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        
        # Create batched payload
        payload = {
            "url": url,
            "batch_size": len(batch_data),
            "updates": batch_data
        }
        
        try:
            logging.info(f"Sending batched data for {url}: {len(batch_data)} updates")
            response = requests.post(self.service_url, headers=headers, json=payload, timeout=5)
            
            if response.status_code == 200:
                logging.info(f"Batch sent successfully for {url}: {len(batch_data)} updates")
            else:
                logging.error(f"Failed to send batch. Status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Error sending batched data: {str(e)}")
    
    def flush_all(self) -> None:
        """Flush all pending batches immediately."""
        with self._lock:
            urls_to_flush = list(self._batches.keys())
            for url in urls_to_flush:
                if self._batches[url]:
                    self._flush_batch_locked(url)
    
    def _background_flusher(self) -> None:
        """Background thread that periodically flushes old batches."""
        while not self._stop_event.is_set():
            time.sleep(1.0)  # Check every second
            
            with self._lock:
                current_time = time.time()
                urls_to_flush = []
                
                for url, last_flush in self._last_flush_time.items():
                    if self._batches[url] and (current_time - last_flush) >= self.flush_interval:
                        urls_to_flush.append(url)
                
                for url in urls_to_flush:
                    self._flush_batch_locked(url)
    
    def _start_background_flusher(self) -> None:
        """Start the background flushing thread."""
        self._flush_thread = threading.Thread(
            target=self._background_flusher,
            daemon=True,
            name="BatchedDataFlusher"
        )
        self._flush_thread.start()
        logging.info("Background batch flusher started")
    
    def shutdown(self) -> None:
        """Gracefully shutdown the batcher."""
        logging.info("Shutting down batched data service...")
        self._stop_event.set()
        
        # Flush all pending data
        self.flush_all()
        
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)
        
        logging.info("Batched data service shutdown complete")


# Global singleton instance
_batch_service: Optional[BatchedCricketDataService] = None
_batch_service_lock = threading.Lock()


def get_batch_service() -> BatchedCricketDataService:
    """Get or create the global batch service instance."""
    global _batch_service
    
    if _batch_service is None:
        with _batch_service_lock:
            if _batch_service is None:
                _batch_service = BatchedCricketDataService(
                    max_batch_size=int(os.getenv('BATCH_SIZE', '10')),
                    flush_interval=float(os.getenv('BATCH_FLUSH_INTERVAL', '5.0'))
                )
    
    return _batch_service


def get_bearer_token():
    """Fetches the bearer token for authentication from local backend."""
    token_url = os.getenv('TOKEN_URL', 'http://127.0.0.1:8099/token/generate-token')
    
    credentials = {
        "username": "tanmay",
        "password": "tanmay"
    }
    
    try:
        logging.info("Requesting bearer token from token endpoint.")
        response = requests.post(token_url, json=credentials, timeout=5)
        
        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get("token")
            logging.info("Bearer token obtained successfully.")
            
            # Update batch service with new token
            batch_service = get_batch_service()
            batch_service.set_bearer_token(token)
            
            return token
        else:
            logging.error(f"Failed to obtain bearer token. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while obtaining bearer token: {str(e)}")
    
    return None


def send_cricket_data_to_service_batched(data, bearer_token, url):
    """
    Queue cricket data for batched sending (optimized version).
    
    This replaces the old send_cricket_data_to_service function with batching.
    Instead of sending immediately, data is queued and sent in batches.
    """
    batch_service = get_batch_service()
    
    # Update token if provided
    if bearer_token:
        batch_service.set_bearer_token(bearer_token)
    
    # Queue the data for batching
    batch_service.queue_update(data, url)


def send_cricket_data_to_service(data, bearer_token, url):
    """
    Original function - kept for backwards compatibility.
    Calls the batched version internally.
    """
    send_cricket_data_to_service_batched(data, bearer_token, url)


def add_live_matches(data, bearer_token):
    """Add live matches (not batched - called infrequently)."""
    service_url = os.getenv('ADD_LIVE_MATCHES_URL', 'http://127.0.0.1:8099/cricket-data/add-live-matches')
    
    headers = {"Content-Type": "application/json"}
    
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    
    try:
        payload = json.dumps(data)
        logging.info(f"Payload: {payload}")
        response = requests.post(service_url, headers=headers, data=payload, timeout=5)
        
        if response.status_code == 200:
            logging.info("Live matches data added successfully.")
        else:
            logging.error(f"Failed to add live matches data. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while adding live matches data: {str(e)}")


def send_data_to_api_endpoint(data, bearer_token, url, api_endpoint=None):
    """Send match info (not batched - called once per match)."""
    if api_endpoint is None:
        api_endpoint = os.getenv('API_ENDPOINT', 'http://127.0.0.1:8099/cricket-data/match-info/save')
    
    headers = {"Content-Type": "application/json"}
    
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
        
        json_payload_str = json.dumps(json_payload)
        logging.debug(f"Serialized JSON payload: {json_payload_str}")
        logging.info(f"Sending data to API endpoint: {api_endpoint}")
        
        response = requests.post(api_endpoint, headers=headers, data=json_payload_str, timeout=5)
        
        if 200 <= response.status_code < 300:
            logging.info("Data sent successfully to the API endpoint.")
            return True
        else:
            logging.error(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logging.error(f"An error occurred while sending data: {str(e)}", exc_info=True)
        return False
