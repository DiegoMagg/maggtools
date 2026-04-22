from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from pathlib import Path

import streamlit as st
from cryptography.fernet import Fernet, InvalidToken

from nfse import ENVIRONMENTS, carregar_configuracoes, init_db, proximo_numero_dps, salvar_configuracoes

CONFIG_KEY_FILE = Path('.nfe_config.key')
CONFIG_DEFAULTS = {
    'config_ambiente': next(iter(ENVIRONMENTS.keys())),
    'config_proximo_numero_nfse': 1,
    'config_pfx_path': '1009580140.pfx',
    'config_pfx_password_input': '',
    'config_pfx_password_resolved': '',
    'config_has_saved_pfx_password': False,
    'config_timeout': 60,
    'config_max_tentativas': 10,
    'config_insecure': False,
    'config_somente_assinar': False,
}


def config_db_path() -> Path:
    return Path('nfse.db')


def _get_or_create_config_key() -> bytes:
    if CONFIG_KEY_FILE.exists():
        return CONFIG_KEY_FILE.read_bytes().strip()
    seed = f'{Path.cwd()}::nfe-config-key'.encode()
    key = urlsafe_b64encode(sha256(seed).digest())
    CONFIG_KEY_FILE.write_bytes(key)
    CONFIG_KEY_FILE.chmod(0o600)
    return key


def _encrypt_secret(value: str) -> str:
    cipher = Fernet(_get_or_create_config_key())
    return cipher.encrypt(value.encode('utf-8')).decode('utf-8')


def _decrypt_secret(value: str) -> str:
    cipher = Fernet(_get_or_create_config_key())
    return cipher.decrypt(value.encode('utf-8')).decode('utf-8')


def init_config_state() -> None:
    config_keys = list(CONFIG_DEFAULTS.keys())
    should_reload_from_db = (not st.session_state.get('config_loaded_from_db', False)) or any(
        key not in st.session_state for key in config_keys
    )

    for key, value in CONFIG_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not should_reload_from_db:
        return

    db_path = config_db_path()
    init_db(db_path)
    saved = carregar_configuracoes(db_path)
    if saved:
        st.session_state['config_pfx_path'] = saved.get(
            'pfx_path',
            st.session_state['config_pfx_path'],
        )
        password_resolved = ''
        pfx_password_enc = saved.get('pfx_password_enc', '')
        if pfx_password_enc.strip():
            try:
                password_resolved = _decrypt_secret(pfx_password_enc)
            except InvalidToken:
                password_resolved = ''
        elif saved.get('pfx_password', '').strip():
            password_resolved = saved.get('pfx_password', '')
            salvar_configuracoes(db_path, {'pfx_password_enc': _encrypt_secret(password_resolved)})

        st.session_state['config_pfx_password_resolved'] = password_resolved
        st.session_state['config_has_saved_pfx_password'] = bool(password_resolved.strip())
        proximo_numero_db = proximo_numero_dps(db_path)
        st.session_state['config_proximo_numero_nfse'] = max(
            int(saved.get('proximo_numero_nfse', st.session_state['config_proximo_numero_nfse'])),
            int(proximo_numero_db),
        )
        st.session_state['config_timeout'] = int(saved.get('timeout', st.session_state['config_timeout']))
        st.session_state['config_max_tentativas'] = int(
            saved.get('max_tentativas', st.session_state['config_max_tentativas'])
        )
        st.session_state['config_insecure'] = (
            saved.get(
                'insecure',
                '1' if st.session_state['config_insecure'] else '0',
            )
            == '1'
        )
        st.session_state['config_somente_assinar'] = (
            saved.get(
                'somente_assinar',
                '1' if st.session_state['config_somente_assinar'] else '0',
            )
            == '1'
        )
    runtime_ambiente = str(st.session_state.get('runtime_ambiente', '')).strip().lower()
    if runtime_ambiente in ENVIRONMENTS:
        st.session_state['config_ambiente'] = runtime_ambiente
    st.session_state['config_loaded_from_db'] = True


def save_config_to_db() -> None:
    db_path = config_db_path()
    init_db(db_path)
    saved = carregar_configuracoes(db_path)
    password_input = str(st.session_state.get('config_pfx_password_input', ''))
    pfx_password_enc = saved.get('pfx_password_enc', '')
    if password_input.strip():
        pfx_password_enc = _encrypt_secret(password_input)

    salvar_configuracoes(
        db_path,
        {
            'proximo_numero_nfse': str(int(st.session_state.get('config_proximo_numero_nfse', 1))),
            'pfx_path': str(st.session_state.get('config_pfx_path', '')),
            'pfx_password_enc': pfx_password_enc,
            'timeout': str(int(st.session_state.get('config_timeout', 60))),
            'max_tentativas': str(int(st.session_state.get('config_max_tentativas', 10))),
            'insecure': '1' if bool(st.session_state.get('config_insecure', False)) else '0',
            'somente_assinar': '1' if bool(st.session_state.get('config_somente_assinar', False)) else '0',
        },
    )
    st.session_state['config_pfx_password_resolved'] = (
        password_input
        if password_input.strip()
        else str(st.session_state.get('config_pfx_password_resolved', ''))
    )
    st.session_state['config_has_saved_pfx_password'] = bool(
        st.session_state['config_pfx_password_resolved'].strip()
    )
    st.session_state['config_clear_pfx_input_next_run'] = True
