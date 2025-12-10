PYTHON_FILES=crex_scraper_python *.py

.PHONY: lint lint-fix format requirements-dev

lint:
	black --check $(PYTHON_FILES)
	isort --check-only $(PYTHON_FILES)
	flake8 $(PYTHON_FILES)

lint-fix: format

format:
	isort $(PYTHON_FILES)
	black $(PYTHON_FILES)

requirements-dev:
	pip install -r requirements-dev.txt
