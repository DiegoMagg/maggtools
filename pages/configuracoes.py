from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from nfse import (
    Prestador,
    certificate_identity_from_pfx,
    init_db,
    obter_prestador,
    salvar_configuracoes,
    salvar_prestador,
)
from page_layout import render_page
from ui_config import config_db_path, init_config_state, save_config_to_db


def _sync_checkbox_state(widget_key: str, state_key: str) -> None:
    st.session_state[state_key] = bool(st.session_state.get(widget_key, False))
    _persist_technical_config()


def _init_prestador_form_state(prestador: Prestador | None) -> None:
    prestador_state_keys = (
        'config_prestador_cnpj',
        'config_prestador_inscricao_municipal',
        'config_prestador_razao_social',
        'config_prestador_telefone',
        'config_prestador_email',
    )
    missing_prestador_keys = any(key not in st.session_state for key in prestador_state_keys)
    if st.session_state.get('config_prestador_form_initialized', False) and not missing_prestador_keys:
        return
    st.session_state['config_prestador_cnpj'] = '' if prestador is None else prestador.cnpj
    st.session_state['config_prestador_inscricao_municipal'] = (
        '' if prestador is None else prestador.inscricao_municipal
    )
    st.session_state['config_prestador_razao_social'] = '' if prestador is None else prestador.razao_social
    st.session_state['config_prestador_telefone'] = (
        '' if prestador is None or prestador.telefone is None else prestador.telefone
    )
    st.session_state['config_prestador_email'] = (
        '' if prestador is None or prestador.email is None else prestador.email
    )
    st.session_state['config_prestador_form_initialized'] = True


def _none_if_blank(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _digits_only(value: str) -> str:
    return re.sub(r'\D', '', value)


def _pfx_validade_caption(pfx_path_texto: str) -> str:
    password = (
        str(st.session_state.get('config_pfx_password_input', '')).strip()
        or str(st.session_state.get('config_pfx_password_resolved', '')).strip()
    )
    if not password:
        return 'validade indisponível (informe a senha do PFX)'
    try:
        identity = certificate_identity_from_pfx(Path(pfx_path_texto), password)
        validade_fim_iso = identity.get('validade_fim_iso', '').strip()
        if not validade_fim_iso:
            return 'validade indisponível'
        validade_fim = datetime.fromisoformat(validade_fim_iso).date()
    except Exception:
        return 'validade indisponível'

    dias_restantes = (validade_fim - date.today()).days
    if dias_restantes < 0:
        return f'certificado expirado ha {abs(dias_restantes)} dias'
    if dias_restantes == 0:
        return 'certificado expira hoje'
    return f'expira em {dias_restantes} dias'


def _try_fill_prestador_from_pfx() -> None:
    pfx_path_texto = str(st.session_state.get('config_pfx_path', '')).strip()
    password = (
        str(st.session_state.get('config_pfx_password_input', '')).strip()
        or str(st.session_state.get('config_pfx_password_resolved', '')).strip()
    )
    if not pfx_path_texto:
        st.error('Informe o caminho do arquivo PFX.')
        return
    if not password:
        st.warning('PFX carregado. Informe a senha para preencher os dados do prestador.')
        return

    pfx_path = Path(pfx_path_texto)
    if not pfx_path.exists():
        st.error(f'Arquivo PFX não encontrado: `{pfx_path}`')
        return

    try:
        identity = certificate_identity_from_pfx(pfx_path, password)
    except Exception as exc:
        st.error(f'Falha ao carregar dados do PFX: {exc}')
        return

    if identity.get('cnpj', '').strip():
        st.session_state['config_prestador_cnpj'] = identity['cnpj'].strip()
    if identity.get('razao_social', '').strip():
        st.session_state['config_prestador_razao_social'] = identity['razao_social'].strip()
    if identity.get('email', '').strip():
        st.session_state['config_prestador_email'] = identity['email'].strip()
    st.success('Campos possíveis do prestador preenchidos com o PFX.')


def _persist_technical_config() -> None:
    db_path = config_db_path()
    init_db(db_path)
    salvar_configuracoes(
        db_path,
        {
            'timeout': str(int(st.session_state.get('config_timeout', 60))),
            'max_tentativas': str(int(st.session_state.get('config_max_tentativas', 10))),
            'insecure': '1' if bool(st.session_state.get('config_insecure', False)) else '0',
            'somente_assinar': '1' if bool(st.session_state.get('config_somente_assinar', False)) else '0',
        },
    )


def main() -> None:
    st.set_page_config(page_title='Configurações', page_icon='⚙️', layout='wide')
    init_config_state()
    st.session_state['config_insecure_widget'] = bool(st.session_state.get('config_insecure', False))
    st.session_state['config_somente_assinar_widget'] = bool(
        st.session_state.get('config_somente_assinar', False)
    )
    if st.session_state.get('config_clear_pfx_input_next_run', False):
        st.session_state['config_pfx_password_input'] = ''
        st.session_state['config_clear_pfx_input_next_run'] = False

    db_path = config_db_path()
    init_db(db_path)
    _init_prestador_form_state(obter_prestador(db_path))

    with render_page('Configurações', 'Defina os parâmetros técnicos usados na geração da NFS-e.'):
        st.markdown('### Configurações técnicas')
        col1, col2 = st.columns([1, 1])
        with col1:
            st.number_input(
                'Timeout (segundos)',
                min_value=5,
                max_value=300,
                step=5,
                key='config_timeout',
                on_change=_persist_technical_config,
            )
        with col2:
            st.number_input(
                'Max tentativas (E0014)',
                min_value=1,
                max_value=100,
                step=1,
                key='config_max_tentativas',
                on_change=_persist_technical_config,
            )
            st.checkbox(
                'Não validar certificado TLS',
                key='config_insecure_widget',
                on_change=_sync_checkbox_state,
                args=('config_insecure_widget', 'config_insecure'),
            )
            st.checkbox(
                'Somente assinar (não enviar)',
                key='config_somente_assinar_widget',
                on_change=_sync_checkbox_state,
                args=('config_somente_assinar_widget', 'config_somente_assinar'),
            )

        if st.button('Salvar configurações', type='primary'):
            save_config_to_db()
            st.success('Configurações salvas no banco de dados.')

    with st.container(border=True):
        st.markdown('### Prestador')
        st.caption('Cadastro único do prestador e dados do certificado digital (PFX).')
        st.markdown(
            """
            <style>
                div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] {
                    min-height: 2.5rem;
                    max-height: 2.4rem;
                    padding: 0.2rem 0.5rem;
                    display: flex;
                    align-items: center;
                }
                div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] button {
                    font-size: 0.8rem;
                    padding: 0.1rem 0.8rem;
                    min-height: 1.7rem;
                    margin-top: 0.2rem;
                }
                div[data-testid="stFileUploader"] small {
                    display: none;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        pfx_col1, pfx_col2 = st.columns(2)
        with pfx_col1:
            pfx_path_atual = str(st.session_state.get('config_pfx_path', '')).strip()
            uploaded_pfx = st.file_uploader(
                'Arquivo PFX *',
                type=['pfx'],
                accept_multiple_files=False,
                key='config_pfx_file',
                help='Se não enviar um novo arquivo, será usado o PFX salvo nas configurações.',
            )
            if uploaded_pfx is not None:
                nome_arquivo = Path(uploaded_pfx.name).name
                destino = Path(nome_arquivo)
                destino.write_bytes(uploaded_pfx.getvalue())
                st.session_state['config_pfx_path'] = str(destino)
                pfx_path_atual = str(destino)
                _try_fill_prestador_from_pfx()
            if pfx_path_atual:
                validade_caption = _pfx_validade_caption(pfx_path_atual)
                st.caption(f'Arquivo PFX atual: `{pfx_path_atual}` ({validade_caption}).')
            else:
                st.caption('Nenhum arquivo PFX salvo.')
        with pfx_col2:
            st.text_input(
                'Senha do PFX',
                type='password',
                key='config_pfx_password_input',
                placeholder='Digite apenas para cadastrar ou alterar a senha',
            )
            if st.session_state.get('config_has_saved_pfx_password', False):
                st.caption('Senha definida.')
            else:
                st.caption('Senha não definida.')

        col1_p, col2_p, col3_p, col4_p, col5_p = st.columns([1, 1, 2, 1, 1])
        with col1_p:
            st.text_input('CNPJ *', key='config_prestador_cnpj', disabled=True)
        with col2_p:
            st.text_input('Inscrição Municipal *', key='config_prestador_inscricao_municipal')
        with col3_p:
            st.text_input('Razão Social *', key='config_prestador_razao_social', disabled=True)
        with col4_p:
            st.text_input('Telefone', key='config_prestador_telefone')
        with col5_p:
            st.text_input('E-mail', key='config_prestador_email')

        salvar_prestador_clicked = st.button(
            'Salvar prestador',
            type='primary',
            key='config_salvar_prestador_btn',
        )

        if salvar_prestador_clicked:
            save_config_to_db()
            errors: list[str] = []
            cnpj = _digits_only(str(st.session_state.get('config_prestador_cnpj', '')))
            if len(cnpj) != 14:
                errors.append('`CNPJ` deve conter 14 dígitos.')
            if not str(st.session_state.get('config_prestador_inscricao_municipal', '')).strip():
                errors.append('`Inscrição Municipal` é obrigatória.')
            if not str(st.session_state.get('config_prestador_razao_social', '')).strip():
                errors.append('`Razão Social` é obrigatória.')

            if errors:
                for err in errors:
                    st.error(err)
            else:
                salvar_prestador(
                    db_path,
                    Prestador(
                        cnpj=cnpj,
                        inscricao_municipal=str(
                            st.session_state.get('config_prestador_inscricao_municipal', '')
                        ).strip(),
                        razao_social=str(st.session_state.get('config_prestador_razao_social', '')).strip(),
                        telefone=_none_if_blank(str(st.session_state.get('config_prestador_telefone', ''))),
                        email=_none_if_blank(str(st.session_state.get('config_prestador_email', ''))),
                    ),
                )
                st.success('Prestador salvo com sucesso.')


if __name__ == '__main__':
    main()
