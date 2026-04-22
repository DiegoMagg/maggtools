from __future__ import annotations

import argparse
import base64
import gzip
import tempfile
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

DEFAULT_BASE_URL = 'https://sefin.producaorestrita.nfse.gov.br/SefinNacional'


def _cert_and_key_from_pfx(pfx_path: Path, pfx_password: str) -> tuple[str, str]:
    key, cert, _ = pkcs12.load_key_and_certificates(
        pfx_path.read_bytes(),
        pfx_password.encode('utf-8'),
    )
    if key is None or cert is None:
        raise ValueError('Nao foi possivel extrair chave/certificado do PFX para mTLS.')

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert_tmp = tempfile.NamedTemporaryFile('wb', suffix='.pem', delete=False)
    key_tmp = tempfile.NamedTemporaryFile('wb', suffix='.pem', delete=False)
    cert_tmp.write(cert_pem)
    key_tmp.write(key_pem)
    cert_tmp.flush()
    key_tmp.flush()
    cert_tmp.close()
    key_tmp.close()
    return cert_tmp.name, key_tmp.name


def consultar_por_chave(
    base_url: str,
    chave_acesso: str,
    pfx_path: Path,
    pfx_password: str,
    timeout: int,
    verify_ssl: bool,
) -> requests.Response:
    cert_path, key_path = _cert_and_key_from_pfx(pfx_path, pfx_password)
    try:
        url = f"{base_url.rstrip('/')}/nfse/{chave_acesso}"
        return requests.get(
            url,
            timeout=timeout,
            verify=verify_ssl,
            cert=(cert_path, key_path),
        )
    finally:
        Path(cert_path).unlink(missing_ok=True)
        Path(key_path).unlink(missing_ok=True)


def extrair_xml_da_resposta(response_json: dict) -> bytes | None:
    nfse_xml_b64 = response_json.get('nfseXmlGZipB64')
    if not isinstance(nfse_xml_b64, str) or not nfse_xml_b64.strip():
        return None
    return gzip.decompress(base64.b64decode(nfse_xml_b64))


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Consulta NFS-e Nacional por chave de acesso (mTLS com PFX).'
    )
    parser.add_argument('--chave', required=True, help='Chave de acesso da NFS-e.')
    parser.add_argument('--pfx', type=Path, default=Path('1009580140.pfx'), help='Arquivo PFX.')
    parser.add_argument('--pfx-password', required=True, help='Senha do PFX.')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL, help='URL base da API nacional.')
    parser.add_argument('--timeout', type=int, default=60, help='Timeout HTTP em segundos.')
    parser.add_argument('--insecure', action='store_true', help='Nao valida certificado TLS do servidor.')
    parser.add_argument(
        '--output-xml',
        type=Path,
        help='Se informado, salva o XML da nota retornado pela API neste arquivo.',
    )
    args = parser.parse_args()

    response = consultar_por_chave(
        base_url=args.base_url,
        chave_acesso=args.chave,
        pfx_path=args.pfx,
        pfx_password=args.pfx_password,
        timeout=args.timeout,
        verify_ssl=not args.insecure,
    )
    print(f'HTTP {response.status_code}')
    print(response.text)

    if not args.output_xml:
        return 0 if response.ok else 1

    try:
        payload = response.json()
    except ValueError:
        print('Resposta nao esta em JSON; nao foi possivel extrair nfseXmlGZipB64.')
        return 0 if response.ok else 1

    xml_bytes = extrair_xml_da_resposta(payload)
    if xml_bytes is None:
        print('Campo nfseXmlGZipB64 nao encontrado na resposta.')
        return 0 if response.ok else 1

    args.output_xml.parent.mkdir(parents=True, exist_ok=True)
    args.output_xml.write_bytes(xml_bytes)
    print(f'XML salvo em: {args.output_xml}')
    return 0 if response.ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
