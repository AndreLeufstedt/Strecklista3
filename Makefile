# Variables
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: all run install clean migrate reset test

# Default rule: runs the application
all: run

# Runs the application
run:
	$(PYTHON) run.py

# Migrates data from the old database into streck.db (only if database is empty)
migrate:
	$(PYTHON) scripts/migrate_old_db.py

# Resets the database and uploads to clean factory state
reset:
	$(PYTHON) scripts/reset_db.py

# Run tests
test:
	$(PYTHON) -m unittest discover -s tests

# Installs requirements into the virtual environment
install: $(VENV)
	$(PIP) install -r requirements.txt

# Creates the virtual environment if it doesn't exist
$(VENV):
	python3 -m venv $(VENV)

# Clean up generated files and virtual environment
clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +