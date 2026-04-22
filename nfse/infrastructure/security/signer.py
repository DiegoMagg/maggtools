from __future__ import annotations

import tempfile
from datetime import UTC
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509 import NameOID
from lxml import etree as LET
from signxml import XMLSigner, methods, namespaces


def sign_dps_xml(xml_bytes: bytes, reference_id: str, pfx_path: Path, pfx_password: str) -> bytes:
    key, cert, _ = pkcs12.load_key_and_certificates(pfx_path.read_bytes(), pfx_password.encode('utf-8'))
    if key is None or cert is None:
        raise ValueError('Nao foi possivel extrair chave/certificado do PFX.')

    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    root = LET.fromstring(xml_bytes)
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/2001/10/xml-exc-c14n#WithComments',
    )
    # Exige assinatura XMLDSig sem prefixo para o validador nacional.
    signer.namespaces = {None: namespaces.ds}
    signed = signer.sign(root, key=key_pem, cert=cert_pem, reference_uri=f'#{reference_id}')
    return LET.tostring(signed, encoding='utf-8', xml_declaration=True)


def cert_and_key_from_pfx(pfx_path: Path, pfx_password: str) -> tuple[str, str]:
    key, cert, _ = pkcs12.load_key_and_certificates(pfx_path.read_bytes(), pfx_password.encode('utf-8'))
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


def certificate_identity_from_pfx(pfx_path: Path, pfx_password: str) -> dict[str, str]:
    _, cert, _ = pkcs12.load_key_and_certificates(pfx_path.read_bytes(), pfx_password.encode('utf-8'))
    if cert is None:
        raise ValueError('Nao foi possivel extrair certificado do PFX.')
    cnpj, razao_social, email = '', '', ''
    common_names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if common_names:
        razao_social, cnpj = str(common_names[0].value).strip().split(':')
    email_attr = cert.subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)
    if email_attr:
        email = str(email_attr[0].value).strip()
    not_valid_after = (
        cert.not_valid_after_utc
        if hasattr(cert, 'not_valid_after_utc')
        else cert.not_valid_after.replace(tzinfo=UTC)
    )
    return {
        'cnpj': cnpj,
        'razao_social': razao_social,
        'email': email,
        'subject': cert.subject.rfc4514_string(),
        'validade_fim_iso': not_valid_after.isoformat(),
    }
