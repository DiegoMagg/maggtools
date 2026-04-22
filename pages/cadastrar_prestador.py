from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

from nfse import (
    Prestador,
    certificate_identity_from_pfx,
    init_db,
    obter_prestador,
    salvar_prestador,
)
from page_layout import render_page
from ui_config import init_config_state


def _none_if_blank(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _normalize_text(value: str) -> str:
    return ' '.join(value.upper().split())


def _digits_only(value: str) -> str:
    return re.sub(r'\D', '', value)


def _is_coherent_name(cert_name: str, informed_name: str) -> bool:
    cert_norm = _normalize_text(cert_name)
    informed_norm = _normalize_text(informed_name)
    return cert_norm == informed_norm or cert_norm in informed_norm or informed_norm in cert_norm


def main() -> None:
    st.set_page_config(page_title='Cadastrar Prestador', page_icon='🏢', layout='wide')
    db_path = Path('nfse.db')
    init_db(db_path)
    init_config_state()

    prestador_atual = obter_prestador(db_path)
    with render_page(
        'Cadastrar prestador',
        'Mantenha um único prestador no banco. Os dados devem ser compatíveis com o certificado PFX.',
    ):
        if prestador_atual is None:
            st.info('Nenhum prestador cadastrado ainda.')
        else:
            st.caption('Prestador atual carregado para edição.')

        with st.form('form_cadastro_prestador', clear_on_submit=False, border=False):
            cnpj = st.text_input(
                'CNPJ *',
                value='' if prestador_atual is None else prestador_atual.cnpj,
                placeholder='Somente números',
            )
            inscricao_municipal = st.text_input(
                'Inscrição Municipal *',
                value='' if prestador_atual is None else prestador_atual.inscricao_municipal,
            )
            razao_social = st.text_input(
                'Razão Social *',
                value='' if prestador_atual is None else prestador_atual.razao_social,
            )
            col1, col2 = st.columns(2)
            with col1:
                telefone = st.text_input(
                    'Telefone',
                    value=''
                    if prestador_atual is None or prestador_atual.telefone is None
                    else prestador_atual.telefone,
                )
            with col2:
                email = st.text_input(
                    'E-mail',
                    value=''
                    if prestador_atual is None or prestador_atual.email is None
                    else prestador_atual.email,
                )
            submitted = st.form_submit_button('Salvar prestador', type='primary')

    if not submitted:
        return

    errors: list[str] = []
    cnpj_digits = _digits_only(cnpj)
    if len(cnpj_digits) != 14:
        errors.append('`CNPJ` deve conter 14 dígitos.')
    if not inscricao_municipal.strip():
        errors.append('`Inscrição Municipal` é obrigatória.')
    if not razao_social.strip():
        errors.append('`Razão Social` é obrigatória.')

    pfx_path_texto = str(st.session_state.get('config_pfx_path', '')).strip()
    pfx_password = str(st.session_state.get('config_pfx_password_resolved', '')).strip()
    if not pfx_path_texto:
        errors.append('Defina o arquivo PFX em `Configurações` para validar o prestador.')
    if not pfx_password:
        errors.append('Defina a senha do PFX em `Configurações` para validar o prestador.')

    cert_identity: dict[str, str] | None = None
    if not errors:
        pfx_path = Path(pfx_path_texto)
        if not pfx_path.exists():
            errors.append(f'Arquivo PFX não encontrado: `{pfx_path}`')
        else:
            try:
                cert_identity = certificate_identity_from_pfx(pfx_path, pfx_password)
            except Exception as exc:
                errors.append(f'Falha ao ler identidade do certificado PFX: {exc}')

    if cert_identity is not None:
        cert_cnpj = _digits_only(cert_identity.get('cnpj', ''))
        cert_razao = cert_identity.get('razao_social', '').strip()

        if not cert_cnpj:
            errors.append('Não foi possível extrair CNPJ do certificado PFX para validação.')
        elif cert_cnpj != cnpj_digits:
            errors.append('CNPJ informado difere do CNPJ presente no certificado PFX.')
        if not cert_razao:
            errors.append('Não foi possível extrair Razão Social do certificado PFX para validação.')
        elif not _is_coherent_name(cert_razao, razao_social):
            errors.append('Razão Social informada difere da organização presente no certificado PFX.')

    if errors:
        for err in errors:
            st.error(err)
        return

    salvar_prestador(
        db_path,
        Prestador(
            cnpj=cnpj_digits,
            inscricao_municipal=inscricao_municipal.strip(),
            razao_social=razao_social.strip(),
            telefone=_none_if_blank(telefone),
            email=_none_if_blank(email),
        ),
    )
    st.success('Prestador salvo com sucesso.')


if __name__ == '__main__':
    main()
