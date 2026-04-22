install:
	uv sync --dev && \
	uv run pre-commit install --hook-type pre-commit --hook-type pre-push

up:
	uv run streamlit run app.py
