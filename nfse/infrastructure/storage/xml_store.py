from __future__ import annotations

import base64
import gzip
from datetime import datetime
from pathlib import Path


def salvar_xml_retorno_nfse(response_payload: dict, emissoes_dir: Path) -> Path | None:
    nfse_xml_b64 = response_payload.get('nfseXmlGZipB64')
    if not isinstance(nfse_xml_b64, str) or not nfse_xml_b64.strip():
        return None

    xml_gzip = base64.b64decode(nfse_xml_b64)
    xml_bytes = gzip.decompress(xml_gzip)

    data_ref = datetime.now()
    pasta_destino = emissoes_dir / f'{data_ref.year:04d}' / f'{data_ref.month:02d}'
    pasta_destino.mkdir(parents=True, exist_ok=True)

    chave = response_payload.get('chaveAcesso')
    id_dps = response_payload.get('idDps') or response_payload.get('idDPS')
    nome_arquivo = f"{chave or id_dps or data_ref.strftime('%Y%m%d%H%M%S')}.xml"
    destino = pasta_destino / nome_arquivo
    destino.write_bytes(xml_bytes)
    return destino
