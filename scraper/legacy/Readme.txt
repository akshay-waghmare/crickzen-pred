# Crex Scraper

This project uses Playwright to scrape data from a given URL and observe changes in the text content of specific elements.

## Installation

1. Install Playwright: `pip install playwright`
2. Install Browser Binaries: `playwright install`

## Usage

Run the script with the URL you want to observe as an argument:

```sh
python crex_scraper.py <url>
```

The script will launch a headless Chromium browser, navigate to the given URL, and start observing changes in the text content of elements with the class `.result-box span`. If the text content changes, it will print the updated text to the console.

## Functions

- `fetchData(url)`: Launches the browser, navigates to the URL, and starts the observation loop.
- `observeTextChanges(page)`: Observes changes in the text content of specific elements on the page.
- `printUpdatedText(updatedTexts)`: Prints the updated text to the console.

## Error Handling

The script includes basic error handling. If an error occurs during navigation or DOM manipulation, it will print the error to the console and continue running. If an uncaught error occurs, it will print the error and exit.

## Stopping the Script

To stop the script, press Ctrl+C. The script will stop the observation loop and exit.
```

Requirements : 

pip install -r requirements.txt


## Using Docker Installation
1. Install Docker: Follow the instructions at https://docs.docker.com/get-docker/
2. Build the Docker image: `docker build -t crex_scraper .`

## Usage
Run the Docker container with the URL you want to observe as an environment variable:

```sh
docker run -e URL=<url> crex_scraper