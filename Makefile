PYTHON := venv/bin/python
PIP := venv/bin/pip
LLM_MODEL := qwen2.5:7b

.PHONY: venv install pull-model scrape fetch build-db data run all clean clean-data help

help:
	@echo "Targets:"
	@echo "  make venv        create venv/ (Python 3.9+)"
	@echo "  make install     install requirements.txt into venv/"
	@echo "  make pull-model  ollama pull $(LLM_MODEL)"
	@echo "  make scrape      scrape Wikipedia pages -> data/raw/wikipedia/"
	@echo "  make fetch       fetch fixtures/standings -> data/raw/football_api/"
	@echo "  make build-db    chunk + embed + write ChromaDB -> data/processed/chroma_db/"
	@echo "  make data        scrape + fetch + build-db (full dataset refresh)"
	@echo "  make run         streamlit run app.py"
	@echo "  make all         install + data + run"
	@echo "  make clean-data  remove data/raw and data/processed (keeps venv)"
	@echo "  make clean       remove venv/ and data/ entirely"

venv:
	python3 -m venv venv

install: venv
	$(PIP) install -r requirements.txt

pull-model:
	ollama pull $(LLM_MODEL)

scrape:
	$(PYTHON) scripts/scrape_wikipedia.py

fetch:
	$(PYTHON) scripts/fetch_football_api.py

build-db:
	$(PYTHON) scripts/build_vector_store.py

data: scrape fetch build-db

run:
	venv/bin/streamlit run app.py

all: install data run

clean-data:
	rm -rf data/raw data/processed

clean: clean-data
	rm -rf venv
