from __future__ import annotations

import base64
import gzip
from pathlib import Path

import requests

from nfse.infrastructure.security.signer import cert_and_key_from_pfx


def send_signed_dps(
    endpoint: str,
    signed_xml: bytes,
    pfx_path: Path,
    pfx_password: str,
    timeout: int,
    verify_ssl: bool,
) -> requests.Response:
    payload_gzip_b64 = base64.b64encode(gzip.compress(signed_xml)).decode('ascii')
    body = {
        'dpsXmlGZipB64': payload_gzip_b64,
    }

    cert_path, key_path = cert_and_key_from_pfx(pfx_path, pfx_password)
    try:
        return requests.post(
            endpoint,
            json=body,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=timeout,
            verify=verify_ssl,
            cert=(cert_path, key_path),
        )
    finally:
        Path(cert_path).unlink(missing_ok=True)
        Path(key_path).unlink(missing_ok=True)


def response_json_or_fallback(response: requests.Response) -> dict:
    try:
        parsed = response.json()
        return parsed if isinstance(parsed, dict) else {'raw_response': response.text}
    except ValueError:
        return {'raw_response': response.text}


def has_error_code(payload: dict, code: str) -> bool:
    erros = payload.get('erros')
    if not isinstance(erros, list):
        return False
    for err in erros:
        if isinstance(err, dict) and err.get('Codigo') == code:
            return True
    return False
