from playwright.sync_api import sync_playwright
import logging
import json

# Configure logging with in-depth logging capabilities
logging.basicConfig(
    filename='enhanced_match_data_with_detailed_logs.log',
    level=logging.INFO,  # Using DEBUG to capture all levels of logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Function to intercept API responses and modify/remove the `wp` field
def intercept_network_calls_and_modify_w_field(url, remove_wp=False):
    try:
        with sync_playwright() as p:
            logging.debug("Starting Playwright browser...")

            # Launch the browser in non-headless mode to view the UI
            browser = p.chromium.launch(headless=False)  # Set headless=False to see the UI
            logging.info("Browser launched successfully.")

            # Create a new context and page
            context = browser.new_context()
            page = context.new_page()
            logging.info("New page created.")

            # Intercept and modify/remove the API response
            def modify_w_field_response(route, request):
                logging.debug(f"Intercepting request to: {request.url}")
                response = route.fetch()  # Fetch the original response
                
                if "sV3.php" in response.url:
                    try:
                        # Parse the response body
                        api_data = response.json()

                        # Check if 'wp' field exists
                        if 'wp' in api_data:
                            logging.info(f"Original 'wp' field: {api_data['wp']}")

                            if remove_wp:
                                # Remove the 'wp' field completely
                                del api_data['wp']
                                del api_data['R']
                                del api_data['Z']
                                # del api_data['ca']
                                # del api_data['cb']
                                # del api_data['ce']
                                # del api_data['f']
                                # del api_data['g']
                                # del api_data['h']
                                # del api_data['i']
                                del api_data['ats']
                                if 'i' in api_data:
                                    logging.info(f"Original 'i' field: {api_data['i']}")

                                    # Modify the 'i' field with the new value (e.g., '4/0.1' or '4/0.2')
                                    api_data['i'] = "7/0.1"
                                    logging.info(f"Modified 'i' fiel d: {api_data['i']}")
                                """ if 'a' in api_data:
                                    logging.info(f"Original 'a' field: {api_data['a']}")

                                    # Split the 'a' value by the period and swap them
                                    a_values = api_data['a'].split('.')
                                    if len(a_values) == 2:
                                        # Swap the values
                                        a_values[0], a_values[1] = a_values[1], a_values[0]

                                        # Rebuild the 'a' field
                                        api_data['a'] = '.'.join(a_values)
                                        logging.info(f"Modified 'a' field: {api_data['a']}")
                                # del api_data['B']
                                logging.info(f"Removed 'wp' field from the response.") """
                            else:
                                # Modify the 'wp' field: swap between 0 and 1
                                wp_values = api_data['wp'].split(',')
                                if wp_values[-1] == '0':
                                    wp_values[-1] = '1'
                                elif wp_values[-1] == '1':
                                    wp_values[-1] = '0'
                                api_data['wp'] = ','.join(wp_values)
                                logging.info(f"Modified 'wp' field: {api_data['wp']}")

                        # Continue with the modified response
                        route.fulfill(
                            status=response.status,
                            headers=response.headers,
                            body=json.dumps(api_data)  # Send the modified body as JSON
                        )
                    except Exception as e:
                        logging.error(f"Error processing API response: {e}", exc_info=True)
                        route.continue_()  # Continue the original request if an error occurs
                else:
                    route.continue_()

            # Attach the interception listener
            page.route("**/*", modify_w_field_response)

            # Navigate to the match URL
            logging.info(f"Navigating to match URL: {url}")
            page.goto(url, timeout=60000)  # Match URL

            # Keep the browser open to monitor the UI changes
            page.wait_for_timeout(300000)  # Adjust time based on match length

            # Close the browser
            logging.info("Closing the browser.")
            browser.close()

    except Exception as e:
        logging.error(f"Critical error in intercepting network calls: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        # Replace with your match URL
        logging.info("Script started.")
        intercept_network_calls_and_modify_w_field(
            'https://crex.live/scoreboard/R8N/1OF/Qualifier-1/YJ/YL/hh-vs-ll-qualifier-1-entertainers-cricket-league-2024/live', 
            remove_wp=True  # Set to True if you want to remove the `wp` field completely
        )
    except Exception as e:
        logging.critical(f"Uncaught error in main script execution: {e}", exc_info=True)
