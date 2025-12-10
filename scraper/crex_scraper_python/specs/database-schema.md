# Database Schema

## Tables

### scraped_urls
- **url**: TEXT PRIMARY KEY - The URL that has been scraped.
- **deletion_attempts**: INTEGER DEFAULT 0 - The number of attempts made to delete the URL.

### leads
- **id**: INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier for each lead.
- **company_name**: TEXT NOT NULL - The name of the company.
- **website**: TEXT - The website of the company.
- **contact_email**: TEXT - The contact email for the company.
- **phone_number**: TEXT - The phone number for the company.
- **notes**: TEXT - Additional notes about the lead.
- **created_at**: TIMESTAMP DEFAULT CURRENT_TIMESTAMP - The timestamp when the lead was created.