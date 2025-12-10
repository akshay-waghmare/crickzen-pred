# Setup Instructions for Development Environment

## Prerequisites

Before setting up the development environment, ensure you have the following installed:

- Python 3.7 or higher
- pip (Python package installer)
- Git

## Clone the Repository

Start by cloning the repository to your local machine:

```bash
git clone https://github.com/yourusername/crex_scraper_python.git
cd crex_scraper_python
```

## Create a Virtual Environment

It is recommended to use a virtual environment to manage dependencies. You can create one using the following commands:

```bash
python -m venv venv
```

Activate the virtual environment:

- On Windows:

```bash
venv\Scripts\activate
```

- On macOS/Linux:

```bash
source venv/bin/activate
```

## Install Dependencies

Once the virtual environment is activated, install the required dependencies:

```bash
pip install -r requirements.txt
```

For development dependencies, run:

```bash
pip install -r requirements-dev.txt
```

## Environment Variables

Create a `.env` file in the root directory of the project and add the necessary environment variables. You can refer to the `.env.example` file for guidance on what variables are needed.

## Database Setup

The project uses SQLite for the database. The database will be initialized automatically when you run the application for the first time. However, you can manually initialize it by running:

```bash
python src/crex_main_url.py
```

## Running the Application

To start the application, run the following command:

```bash
python src/crex_main_url.py
```

The application will be accessible at `http://127.0.0.1:5000`.

## Additional Information

For more details on how to contribute, deploy, or use the API, please refer to the other documentation files in the `docs` directory.