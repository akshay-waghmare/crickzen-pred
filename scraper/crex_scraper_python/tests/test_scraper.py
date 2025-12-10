import unittest
from unittest.mock import patch, MagicMock
from src.crex_scraper import scrape

class TestScraper(unittest.TestCase):

    @patch('src.crex_scraper.sync_playwright')
    def test_scrape_success(self, mock_playwright):
        # Arrange
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        mock_page.goto.return_value = None
        mock_page.query_selector.return_value = MagicMock()
        mock_page.query_selector_all.return_value = [MagicMock() for _ in range(3)]
        
        # Mock the href attribute for the live divs
        for i, live_div in enumerate(mock_page.query_selector_all.return_value):
            live_div.query_selector.return_value.query_selector.return_value.get_attribute.return_value = f"/match/{i}"

        # Act
        result = scrape(mock_page, "https://crex.live")

        # Assert
        self.assertEqual(result['status'], 'Scraping finished')
        self.assertEqual(len(result['match_urls']), 3)

    @patch('src.crex_scraper.sync_playwright')
    def test_scrape_dom_change_error(self, mock_playwright):
        # Arrange
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        mock_page.goto.return_value = None
        mock_page.query_selector.return_value = None  # Simulate DOM change error

        # Act & Assert
        with self.assertRaises(Exception) as context:
            scrape(mock_page, "https://crex.live")
        self.assertTrue('Cannot locate essential' in str(context.exception))

if __name__ == '__main__':
    unittest.main()