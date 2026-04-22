from __future__ import annotations

import argparse
import os

import streamlit as st

from nfse import ENVIRONMENTS


def _parse_ambiente_cli() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--ambiente', default='producao', choices=['producao', 'homologacao'])
    args, _ = parser.parse_known_args()
    return str(args.ambiente).strip().lower()


def _render_sidebar_footer(ambiente: str) -> None:
    if ambiente == 'homologacao':
        footer_text = 'homologação'
    else:
        footer_text = f"v{os.getenv('MAGGNFSEVERSION', '1.0.0')}"
    with st.sidebar:
        st.markdown(
            f"""
            <style>
                [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
                    padding-bottom: 2.8rem;
                }}
                .menu-footer {{
                    padding: 0.6rem 1rem;
                    text-align: center;
                    font-size: 0.8rem;
                    font-weight: 600;
                    letter-spacing: 0.04em;
                    position: fixed;
                    align-self: center;
                    margin-left: 100px;
                    bottom: 0;
                }}
            </style>
            <div class="menu-footer">{footer_text}</div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    ambiente = _parse_ambiente_cli()
    if ambiente not in ENVIRONMENTS:
        raise ValueError(f'Ambiente inválido: {ambiente}')
    st.session_state['runtime_ambiente'] = ambiente
    st.session_state['config_ambiente'] = ambiente

    navigation = st.navigation(
        [
            st.Page('pages/dashboard.py', title='Dashboard', icon='📊', default=True),
            st.Page('pages/gerar_nfse.py', title='Gerar NFS-e', icon='🧾'),
            st.Page('pages/consultar_nfse.py', title='Consultar NFS-e', icon='🔎'),
            st.Page('pages/importar_nfse.py', title='Importar NFS-e', icon='📥'),
            st.Page('pages/cadastrar_tomador.py', title='Cadastrar tomador', icon='👤'),
            st.Page('pages/configuracoes.py', title='Configurações', icon='⚙️'),
        ]
    )
    _render_sidebar_footer(ambiente)
    navigation.run()


if __name__ == '__main__':
    main()
