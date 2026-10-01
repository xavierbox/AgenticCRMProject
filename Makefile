# 1. Force the use of bash to support the 'source' command
SHELL := /bin/bash

# 2. Run all recipe lines in a single shell session
.ONESHELL:
.PHONY: install clean

VENV := .venv

install:
	@echo "Creating virtual environment..."
	python -m virtualenv $(VENV)
	@echo "Activating and installing requirements..."
	# Now 'source' will work because we are using /bin/bash
	source $(VENV)/bin/activate && pip install -r dataiku_requirements.txt
	@echo -e "\nInstallation complete. Use 'source $(VENV)/bin/activate' to use the environment."

clean:
	rm -rf $(VENV)

