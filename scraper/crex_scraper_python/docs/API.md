# API Documentation

## Overview

This document provides an overview of the API endpoints available in the Cricket Scraper project. Each endpoint is described with its request method, URL, parameters, and response format.

## Base URL

The base URL for all API endpoints is:

```
http://localhost:5000
```

## Endpoints

### 1. Scrape Live Matches

- **URL**: `/scrape-live-matches-link`
- **Method**: `GET`
- **Description**: Starts the scraping process for live matches.
- **Response**:
  - **200 OK**: Scraping started successfully.
    ```json
    {
      "status": "Scraping started"
    }
    ```

### 2. Start Scraping

- **URL**: `/start-scrape`
- **Method**: `POST`
- **Description**: Initiates scraping for a specific URL.
- **Request Body**:
  ```json
  {
    "url": "https://example.com"
  }
  ```
- **Response**:
  - **200 OK**: Scraping started for the specified URL.
    ```json
    {
      "status": "Scraping started for url: https://example.com"
    }
    ```
  - **400 Bad Request**: No URL provided.
    ```json
    {
      "status": "No url provided"
    }
    ```

### 3. Stop Scraping

- **URL**: `/stop-scrape`
- **Method**: `POST`
- **Description**: Stops the scraping process for a specific URL.
- **Request Body**:
  ```json
  {
    "url": "https://example.com"
  }
  ```
- **Response**:
  - **200 OK**: Scraping stopped for the specified URL.
    ```json
    {
      "status": "Stopped scraping for url: https://example.com"
    }
    ```
  - **400 Bad Request**: No scraping task found for the URL or no URL provided.
    ```json
    {
      "status": "No scraping task found for url: https://example.com"
    }
    ```

### 4. Add Lead

- **URL**: `/add-lead`
- **Method**: `POST`
- **Description**: Adds a new lead to the database.
- **Request Body**:
  ```json
  {
    "company_name": "Company Name",
    "website": "https://company.com",
    "contact_email": "contact@company.com",
    "phone_number": "1234567890",
    "notes": "Some notes about the lead"
  }
  ```
- **Response**:
  - **201 Created**: Lead added successfully.
    ```json
    {
      "message": "Lead added successfully",
      "lead_id": 1
    }
    ```
  - **400 Bad Request**: Company name and website are required.
    ```json
    {
      "error": "Company name and website are required"
    }
    ```

### 5. View Leads

- **URL**: `/view-leads`
- **Method**: `GET`
- **Description**: Retrieves a list of all leads.
- **Response**:
  - **200 OK**: List of leads.
    ```json
    {
      "leads": [
        {
          "id": 1,
          "company_name": "Company Name",
          "website": "https://company.com",
          "contact_email": "contact@company.com",
          "phone_number": "1234567890",
          "notes": "Some notes about the lead",
          "created_at": "2023-01-01T00:00:00"
        }
      ]
    }
    ```

### 6. Update Lead

- **URL**: `/update-lead/<int:lead_id>`
- **Method**: `PUT`
- **Description**: Updates an existing lead.
- **Request Body**:
  ```json
  {
    "company_name": "Updated Company Name",
    "website": "https://updatedcompany.com"
  }
  ```
- **Response**:
  - **200 OK**: Lead updated successfully.
    ```json
    {
      "message": "Lead updated successfully"
    }
    ```
  - **404 Not Found**: Lead not found.
    ```json
    {
      "error": "Lead not found"
    }
    ```

### 7. Delete Lead

- **URL**: `/delete-lead/<int:lead_id>`
- **Method**: `DELETE`
- **Description**: Deletes a lead from the database.
- **Response**:
  - **200 OK**: Lead deleted successfully.
    ```json
    {
      "message": "Lead deleted successfully"
    }
    ```
  - **404 Not Found**: Lead not found.
    ```json
    {
      "error": "Lead not found"
    }
    ```

## Conclusion

This API allows for managing scraping tasks and leads effectively. Ensure to handle responses appropriately in your application.