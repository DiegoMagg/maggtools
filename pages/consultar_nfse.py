from __future__ import annotations

import base64
import gzip
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import streamlit as st

from nfse import (
    atualizar_nfse_classificacao,
    contar_nfse_emitidas,
    init_db,
    listar_nfse_emitidas,
    obter_resposta_nfse_por_id,
)
from page_layout import render_page
from ui_config import config_db_path, init_config_state


def _xml_legivel_do_payload(payload: dict) -> str:
    xml_b64 = payload.get('nfseXmlGZipB64')
    if not isinstance(xml_b64, str) or not xml_b64.strip():
        return ''
    try:
        xml_bytes = gzip.decompress(base64.b64decode(xml_b64))
        raiz = ET.fromstring(xml_bytes)
        ET.indent(raiz, space='  ')
        return ET.tostring(raiz, encoding='unicode', xml_declaration=True)
    except Exception:
        return ''


def main() -> None:
    st.set_page_config(page_title='Consultar NFS-e', page_icon='🔎', layout='wide')
    init_config_state()

    with render_page('Consultar notas emitidas', 'Busque e revise NFS-e já emitidas no sistema.'):
        db_path = config_db_path()
        init_db(db_path)
        ambiente = str(st.session_state.get('config_ambiente', 'producao')).strip().lower()

        col_filtro, col_cancelada, col_limite = st.columns([3, 1, 1])
        with col_filtro:
            termo = st.text_input(
                'Buscar por número DPS, chave, CNPJ ou ID DPS',
                value='',
                placeholder='Ex.: 25 ou 314330...',
            ).strip()
        with col_cancelada:
            cancelada_opcao = st.selectbox(
                'Cancelamento',
                options=['todas', 'ativas', 'canceladas'],
                index=0,
            )
        with col_limite:
            itens_por_pagina = int(
                st.selectbox(
                    'Itens por página',
                    options=[12, 24, 48, 96],
                    index=0,
                )
            )

        default_fim = date.today()
        default_inicio = default_fim - timedelta(days=30)
        periodo_col1, periodo_col2 = st.columns(2)
        with periodo_col1:
            data_inicio = st.date_input('Emitida de', value=default_inicio)
        with periodo_col2:
            data_fim = st.date_input('Emitida até', value=default_fim)

        if data_inicio > data_fim:
            st.warning('A data inicial não pode ser maior que a data final.')
            return

        emitida_inicio = f'{data_inicio.isoformat()}T00:00:00'
        emitida_fim = f'{data_fim.isoformat()}T23:59:59'
        cancelada_filtro = {'todas': '', 'ativas': '0', 'canceladas': '1'}[cancelada_opcao]
        total_registros = contar_nfse_emitidas(
            db_path,
            termo=termo,
            emitida_inicio=emitida_inicio,
            emitida_fim=emitida_fim,
            ambiente=ambiente,
            cancelada=cancelada_filtro,
        )

        if total_registros <= 0:
            st.info('Nenhuma NFS-e encontrada com os filtros informados.')
            return

        total_paginas = max(1, (total_registros + itens_por_pagina - 1) // itens_por_pagina)
        pagina_state_key = 'consultar_nfse_pagina'
        pagina_anterior = int(st.session_state.get(pagina_state_key, 1))
        pagina = min(max(pagina_anterior, 1), total_paginas)
        st.session_state[pagina_state_key] = pagina
        offset = (pagina - 1) * itens_por_pagina
        registros = listar_nfse_emitidas(
            db_path,
            limit=itens_por_pagina,
            offset=offset,
            termo=termo,
            emitida_inicio=emitida_inicio,
            emitida_fim=emitida_fim,
            ambiente=ambiente,
            cancelada=cancelada_filtro,
        )
        registros_sem_ambiente = [{k: v for k, v in item.items() if k != 'ambiente'} for item in registros]

        st.caption(
            f'{total_registros} registro(s) encontrado(s). Exibindo página {pagina} de {total_paginas}.'
        )
        st.dataframe(
            registros_sem_ambiente,
            width='stretch',
            hide_index=True,
            column_config={
                'id': st.column_config.NumberColumn('ID', width='small'),
                'numero_dps': st.column_config.NumberColumn('Numero DPS', width='small'),
                'id_dps': st.column_config.TextColumn('ID DPS', width='large'),
                'chave_acesso': st.column_config.TextColumn('Chave de acesso', width='large'),
                'codigo_municipio': st.column_config.TextColumn('Municipio', width='small'),
                'cnpj_prestador': st.column_config.TextColumn('CNPJ prestador', width='medium'),
                'serie': st.column_config.TextColumn('Serie', width='small'),
                'valor_servicos': st.column_config.TextColumn('Valor', width='small'),
                'emitida_em': st.column_config.TextColumn('Emitida em', width='medium'),
                'cancelada': st.column_config.CheckboxColumn('Cancelada', width='small'),
            },
        )
        inicio_janela = max(1, pagina - 1)
        fim_janela = min(total_paginas, pagina + 1)
        paginas_visiveis = list(range(inicio_janela, fim_janela + 1))
        _, nav_center, _ = st.columns([12, 2, 12])
        with nav_center:
            nav_cols = st.columns([1] * (len(paginas_visiveis) + 2), gap='small')
            with nav_cols[0]:
                if st.button(
                    '‹',
                    key='consultar_nfse_page_prev',
                    disabled=pagina <= 1,
                    width='content',
                ):
                    st.session_state[pagina_state_key] = pagina - 1
                    st.rerun()
            for idx, pagina_item in enumerate(paginas_visiveis, start=1):
                with nav_cols[idx]:
                    if st.button(
                        str(pagina_item),
                        key=f'consultar_nfse_page_{pagina_item}',
                        type='primary' if pagina_item == pagina else 'secondary',
                        disabled=pagina_item == pagina,
                        width='content',
                    ):
                        st.session_state[pagina_state_key] = pagina_item
                        st.rerun()
            with nav_cols[-1]:
                if st.button(
                    '›',
                    key='consultar_nfse_page_next',
                    disabled=pagina >= total_paginas,
                    width='content',
                ):
                    st.session_state[pagina_state_key] = pagina + 1
                    st.rerun()
        st.caption(f'Página {pagina} de {total_paginas}')

        ids = [int(item['id']) for item in registros]
        registro_detalhes = int(
            st.selectbox('Selecionar registro para detalhes', options=ids, index=0, width=200)
        )
        registro_atual = next((item for item in registros if int(item['id']) == registro_detalhes), None)
        if registro_atual is not None:
            st.markdown('#### Ajustes da nota')
            ajustes_col1, ajustes_col2 = st.columns([1, 1])
            with ajustes_col1:
                cancelada_nota = st.checkbox(
                    'Nota cancelada',
                    value=bool(registro_atual.get('cancelada', False)),
                    key=f'consultar_nfse_cancelada_{registro_detalhes}',
                )
            with ajustes_col2:
                st.write('')
                st.write('')
                if st.button(
                    'Salvar ajustes', type='primary', key=f'consultar_nfse_salvar_{registro_detalhes}'
                ):
                    atualizado = atualizar_nfse_classificacao(
                        db_path,
                        registro_id=registro_detalhes,
                        ambiente=ambiente,
                        cancelada=cancelada_nota,
                    )
                    if atualizado:
                        st.success('Classificação da nota atualizada.')
                        st.rerun()
                    else:
                        st.error('Não foi possível atualizar a nota selecionada.')

        payload = obter_resposta_nfse_por_id(db_path, int(registro_detalhes)) if registro_detalhes else {}
        xml_legivel = _xml_legivel_do_payload(payload)
        if xml_legivel:
            st.markdown('#### XML da NFS-e')
            st.code(xml_legivel, language='xml')
            st.download_button(
                label='Baixar XML',
                data=xml_legivel.encode('utf-8'),
                file_name=f'nfse_{registro_detalhes}.xml',
                mime='application/xml',
                width='content',
            )
        else:
            st.info('Nenhum XML disponível para o registro selecionado.')


if __name__ == '__main__':
    main()
