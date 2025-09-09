PYTHON?=python
PIP?=pip

.PHONY: setup test lint docs

setup:
	$(PIP) install -r requirements.txt

test:
	pytest -q

docs:
	echo "Docs are under docs/latex"


