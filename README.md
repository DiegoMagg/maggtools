# NFS-e Nacional

Scripts para emissao e consulta consulta de NFS-e no padrao nacional.

## Requisitos

- Python via `uv`
- Certificado A1 (`.pfx`)

## Emissao de NFS-e

### Homologacao

```bash
uv run python gerar_nfse.py \
  --ambiente homologacao \
  --pfx "arquivo.pfx" \
  --pfx-password "SUA_SENHA_AQUI"
```

### Producao

```bash
uv run python gerar_nfse.py \
  --ambiente producao \
  --pfx "arquivo.pfx" \
  --pfx-password "SUA_SENHA_AQUI"
```
