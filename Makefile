install:
	uv sync --dev && \
	uv run pre-commit install --hook-type pre-commit --hook-type pre-push

up-homologacao:
	uv run streamlit run app.py -- --ambiente homologacao

up-producao:
	uv run streamlit run app.py -- --ambiente producao
