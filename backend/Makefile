PYTHON = .venv/bin/python
PIP    = .venv/bin/pip

.PHONY: venv install migrate superuser run

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install -r requirements.txt

migrate:
	$(PYTHON) manage.py migrate

superuser:
	$(PYTHON) manage.py createsuperuser

run:
	$(PYTHON) manage.py runserver
