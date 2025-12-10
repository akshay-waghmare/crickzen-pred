# Deployment Instructions for the Cricket Scraper Application

This document outlines the steps required to deploy the Cricket Scraper application. Follow these instructions to ensure a successful deployment.

## Prerequisites

1. **Environment Setup**
   - Ensure you have Python 3.7 or higher installed.
   - Install the required dependencies listed in `requirements.txt` and `requirements-dev.txt`.

2. **Database Setup**
   - Ensure that the SQLite database file (`url_state.db`) is created and accessible.
   - The application will automatically initialize the database on the first run.

3. **Environment Variables**
   - Create a `.env` file in the root directory of the project based on the `.env.example` file.
   - Configure the necessary environment variables, including any API keys or secrets required for external services.

## Deployment Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/crex_scraper_python.git
   cd crex_scraper_python
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Run Database Initialization**
   - The database will be initialized automatically when you run the application for the first time. Ensure that the application has write access to the directory where the database file will be created.

4. **Start the Application**
   ```bash
   python src/crex_main_url.py
   ```
   - The application will start running on `http://0.0.0.0:5000`.

5. **Access the API**
   - You can access the API endpoints at `http://localhost:5000`. Refer to the `API.md` document for details on available endpoints.

## Monitoring and Maintenance

- Monitor the application logs for any errors or warnings. Logs are stored in `crex_scraper.log`.
- Regularly check for updates to dependencies and apply them as necessary.

## Troubleshooting

- If you encounter issues during deployment, check the following:
  - Ensure all environment variables are set correctly.
  - Verify that the database file is created and accessible.
  - Review the application logs for any error messages.

By following these steps, you should be able to successfully deploy the Cricket Scraper application. For further assistance, refer to the `CONTRIBUTING.md` document or reach out to the project maintainers.