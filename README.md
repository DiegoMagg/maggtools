# NFS-e Nacional

Scripts para emissao e consulta consulta de NFS-e no padrao nacional.

## Requisitos

- Python via `uv`
- Certificado A1 (`.pfx`)

## Emissao de NFS-e

### Homologacao

```bash
uv run python -m nfse.interfaces.cli_emitir \
  --ambiente homologacao \
  --pfx "arquivo.pfx" \
  --pfx-password "SUA_SENHA_AQUI" \
  --data-emissao "2026-04-22T13:46:01-03:00" \
  --valor-reais "5.00" \
  --valor-dolar "1.00"
```

### Producao

```bash
uv run python -m nfse.interfaces.cli_emitir \
  --ambiente producao \
  --pfx "arquivo.pfx" \
  --pfx-password "SUA_SENHA_AQUI" \
  --data-emissao "2026-04-22T13:46:01-03:00" \
  --valor-reais "5.00" \
  --valor-dolar "1.00"
```

## Interface web

```bash
uv run streamlit run app.py
```

Na tela, confira os blocos **Emissor (Prestador)** e **Tomador** antes de clicar em **Gerar NFS-e**.
