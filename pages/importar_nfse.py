from __future__ import annotations

import base64
import gzip
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime

import streamlit as st

from nfse import (
    existe_nfse_por_identificadores,
    init_db,
    proximo_numero_dps,
    registrar_nf_importada,
)
from page_layout import render_page
from ui_config import config_db_path, init_config_state

NAMESPACE_NFSE = 'http://www.sped.fazenda.gov.br/nfse'
NS = {'nfse': NAMESPACE_NFSE}


def _to_payload(xml_bytes: bytes) -> dict[str, str]:
    xml_b64 = base64.b64encode(gzip.compress(xml_bytes)).decode('ascii')
    return {'nfseXmlGZipB64': xml_b64}


def _parse_import_metadata(xml_bytes: bytes, fallback_numero: int) -> dict[str, str | int]:
    raiz = ET.fromstring(xml_bytes)
    if raiz.tag.startswith('{'):
        namespace = raiz.tag[1:].split('}')[0]
        ns = {'nfse': namespace}
    else:
        ns = NS

    def get(path: str) -> str:
        node = raiz.find(path, ns)
        if node is None or node.text is None:
            return ''
        return node.text.strip()

    numero_dps_texto = get('.//nfse:DPS/nfse:infDPS/nfse:nDPS') or get('.//nfse:infDPS/nfse:nDPS')
    try:
        numero_dps = int(numero_dps_texto) if numero_dps_texto else int(fallback_numero)
    except ValueError:
        numero_dps = int(fallback_numero)

    inf_dps = raiz.find('.//nfse:DPS/nfse:infDPS', ns)
    if inf_dps is None:
        inf_dps = raiz.find('.//nfse:infDPS', ns)
    id_dps = '' if inf_dps is None else str(inf_dps.attrib.get('Id', '')).strip()

    inf_nfse = raiz.find('.//nfse:infNFSe', ns)
    chave_acesso = '' if inf_nfse is None else str(inf_nfse.attrib.get('Id', '')).strip()

    codigo_municipio = get('.//nfse:emit/nfse:enderNac/nfse:cMun')
    cnpj_prestador = get('.//nfse:emit/nfse:CNPJ') or get('.//nfse:prest/nfse:CNPJ')
    serie = get('.//nfse:DPS/nfse:infDPS/nfse:serie') or get('.//nfse:infDPS/nfse:serie')
    valor_servicos = (
        get('.//nfse:DPS/nfse:infDPS/nfse:valores/nfse:vServPrest/nfse:vServ')
        or get('.//nfse:valores/nfse:vLiq')
        or '0.00'
    )
    emitida_em = (
        get('.//nfse:DPS/nfse:infDPS/nfse:dhEmi')
        or get('.//nfse:infDPS/nfse:dhEmi')
        or get('.//nfse:infNFSe/nfse:dhProc')
        or get('.//nfse:dhProc')
    )
    try:
        emitida_em_iso = datetime.fromisoformat(emitida_em).isoformat(timespec='seconds')
    except Exception:
        emitida_em_iso = ''

    return {
        'numero_dps': numero_dps,
        'id_dps': id_dps,
        'chave_acesso': chave_acesso,
        'codigo_municipio': codigo_municipio,
        'cnpj_prestador': cnpj_prestador,
        'serie': serie,
        'valor_servicos': valor_servicos,
        'emitida_em': emitida_em_iso,
    }


def _numero_dps_disponivel(db_path, numero_dps: int) -> int:
    candidato = int(numero_dps)
    while True:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                'SELECT 1 FROM nfse_emitidas WHERE numero_dps = ? LIMIT 1',
                (candidato,),
            ).fetchone()
        if row is None:
            return candidato
        candidato = int(proximo_numero_dps(db_path))


def main() -> None:
    st.set_page_config(page_title='Importar NFS-e', page_icon='📥', layout='wide')
    init_config_state()

    with render_page('Importar NFS-e', 'Importe um ou mais arquivos XML já emitidos no webservice.'):
        db_path = config_db_path()
        init_db(db_path)
        ambiente = str(st.session_state.get('config_ambiente', 'producao')).strip().lower()

        arquivos = st.file_uploader(
            'Arquivos XML da NFS-e',
            type=['xml'],
            accept_multiple_files=True,
            help='Você pode selecionar vários arquivos XML para importação em lote.',
        )

        if not arquivos:
            st.info('Selecione ao menos um arquivo XML para iniciar a importação.')
            return

        if st.button('Importar XML(s)', type='primary'):
            sucesso = 0
            falhas = 0
            ignorados = 0
            for arquivo in arquivos:
                try:
                    xml_bytes = arquivo.getvalue()
                    metadata = _parse_import_metadata(xml_bytes, fallback_numero=proximo_numero_dps(db_path))
                    if existe_nfse_por_identificadores(
                        db_path,
                        id_dps=str(metadata['id_dps']),
                        chave_acesso=str(metadata['chave_acesso']),
                    ):
                        ignorados += 1
                        st.info(f'Arquivo `{arquivo.name}` já importado. Nenhuma ação executada.')
                        continue
                    numero_dps = _numero_dps_disponivel(db_path, int(metadata['numero_dps']))
                    payload = _to_payload(xml_bytes)
                    payload['origem_importacao'] = 'arquivo_xml'
                    payload['arquivo_origem'] = arquivo.name
                    registrar_nf_importada(
                        db_path,
                        numero_dps=numero_dps,
                        ambiente=str(ambiente),
                        id_dps=str(metadata['id_dps']),
                        chave_acesso=str(metadata['chave_acesso']),
                        codigo_municipio=str(metadata['codigo_municipio']),
                        cnpj_prestador=str(metadata['cnpj_prestador']),
                        serie=str(metadata['serie']),
                        valor_servicos=str(metadata['valor_servicos']),
                        resposta_payload=payload,
                        emitida_em=str(metadata.get('emitida_em', '')),
                    )
                    sucesso += 1
                except Exception as exc:
                    falhas += 1
                    st.error(f'Falha ao importar `{arquivo.name}`: {exc}')

            if sucesso:
                st.success(f'{sucesso} arquivo(s) importado(s) com sucesso.')
            if falhas:
                st.warning(f'{falhas} arquivo(s) não foram importados.')


if __name__ == '__main__':
    main()
