import unittest
import sqlite3
from src.crex_main_url import initialize_database, store_urls, load_previous_urls

class TestDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the database before any tests are run."""
        initialize_database()

    def setUp(self):
        """Set up a fresh database connection for each test."""
        self.conn = sqlite3.connect('url_state.db')
        self.cursor = self.conn.cursor()

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_store_urls(self):
        """Test storing URLs in the database."""
        urls = ['https://crex.live/test1', 'https://crex.live/test2']
        store_urls(urls)

        self.cursor.execute("SELECT url FROM scraped_urls")
        stored_urls = [row[0] for row in self.cursor.fetchall()]
        self.assertEqual(set(stored_urls), set(urls))

    def test_load_previous_urls(self):
        """Test loading previously stored URLs."""
        urls = ['https://crex.live/test3', 'https://crex.live/test4']
        store_urls(urls)

        loaded_urls = load_previous_urls()
        self.assertEqual(set(loaded_urls), set(urls))

    def test_database_initialization(self):
        """Test if the database initializes correctly."""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in self.cursor.fetchall()]
        self.assertIn('scraped_urls', tables)
        self.assertIn('leads', tables)

if __name__ == '__main__':
    unittest.main()