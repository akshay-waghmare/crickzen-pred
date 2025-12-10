import unittest
from flask import json
from crex_scraper_python.src.crex_main_url import app

class APITestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_scrape_live_matches(self):
        response = self.app.get('/scrape-live-matches-link')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Scraping started', str(response.data))

    def test_add_lead(self):
        response = self.app.post('/add-lead', 
                                 data=json.dumps({
                                     'company_name': 'Test Company',
                                     'website': 'https://testcompany.com',
                                     'contact_email': 'contact@testcompany.com',
                                     'phone_number': '1234567890',
                                     'notes': 'Test notes'
                                 }),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('Lead added successfully', str(response.data))

    def test_view_leads(self):
        response = self.app.get('/view-leads')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(json.loads(response.data), dict)

    def test_update_lead(self):
        # First, add a lead to update
        add_response = self.app.post('/add-lead', 
                                      data=json.dumps({
                                          'company_name': 'Update Company',
                                          'website': 'https://updatecompany.com',
                                          'contact_email': 'contact@updatecompany.com',
                                          'phone_number': '0987654321',
                                          'notes': 'Update notes'
                                      }),
                                      content_type='application/json')
        lead_id = json.loads(add_response.data)['lead_id']

        # Now, update the lead
        update_response = self.app.put(f'/update-lead/{lead_id}', 
                                        data=json.dumps({
                                            'company_name': 'Updated Company',
                                            'website': 'https://updatedcompany.com'
                                        }),
                                        content_type='application/json')
        self.assertEqual(update_response.status_code, 200)
        self.assertIn('Lead updated successfully', str(update_response.data))

    def test_delete_lead(self):
        # First, add a lead to delete
        add_response = self.app.post('/add-lead', 
                                      data=json.dumps({
                                          'company_name': 'Delete Company',
                                          'website': 'https://deletecompany.com',
                                          'contact_email': 'contact@deletecompany.com',
                                          'phone_number': '1122334455',
                                          'notes': 'Delete notes'
                                      }),
                                      content_type='application/json')
        lead_id = json.loads(add_response.data)['lead_id']

        # Now, delete the lead
        delete_response = self.app.delete(f'/delete-lead/{lead_id}')
        self.assertEqual(delete_response.status_code, 200)
        self.assertIn('Lead deleted successfully', str(delete_response.data))

if __name__ == '__main__':
    unittest.main()