.PHONY: install data test lint dashboard report clean

install:        ## Create venv and install all deps
	uv sync

data:           ## Generate the synthetic portfolio (Phase 1)
	uv run python -m cacm.generate

test:           ## Run the test suite
	uv run pytest

lint:           ## Lint with ruff
	uv run ruff check .

dashboard:      ## Launch the Streamlit dashboard on the committed sample
	uv run streamlit run src/cacm/dashboard.py

report:         ## Execute the notebooks in order (Phase 4+)
	uv run jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb

clean:
	rm -rf .pytest_cache .ruff_cache data/raw/*.parquet
