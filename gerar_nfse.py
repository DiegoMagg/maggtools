from __future__ import annotations

import argparse
import base64
import gzip
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from xml.etree import ElementTree as ET

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree as LET
from signxml import XMLSigner, methods, namespaces


@dataclass(frozen=True)
class Prestador:
    cnpj: str
    inscricao_municipal: str
    razao_social: str
    telefone: str | None
    email: str | None


@dataclass(frozen=True)
class Tomador:
    razao_social: str
    email: str | None
    logradouro: str
    numero: str
    bairro: str
    codigo_pais: str | None
    codigo_end_postal: str | None
    cidade_exterior: str | None
    estado_exterior: str | None


@dataclass(frozen=True)
class Servico:
    item_lista_servico: str
    codigo_tributacao_municipio: str
    codigo_nbs: str | None
    discriminacao: str
    codigo_municipio: str
    valor_servicos: Decimal
    iss_retido: int


@dataclass(frozen=True)
class RpsData:
    numero: str
    serie: str
    data_emissao: datetime
    competencia: str
    prestador: Prestador
    tomador: Tomador
    servico: Servico


NAMESPACE_NFSE: Final[str] = 'http://www.sped.fazenda.gov.br/nfse'
VERSAO_DPS: Final[str] = '1.01'
ENVIRONMENTS: Final[dict[str, dict[str, int | str]]] = {
    'homologacao': {
        'endpoint': 'https://sefin.producaorestrita.nfse.gov.br/SefinNacional/nfse',
        'ambiente': 2,
        'serie': '900',
        'enviar_im_prestador': False,
    },
    'producao': {
        'endpoint': 'https://sefin.nfse.gov.br/SefinNacional/nfse',
        'ambiente': 1,
        'serie': '70000',
        'enviar_im_prestador': True,
    },
}


def dados_fixos_nfse(numero_dps: int, serie: str) -> RpsData:
    return RpsData(
        numero=str(numero_dps),
        serie=serie,
        data_emissao=datetime.fromisoformat('2026-04-22T13:46:01-03:00'),
        competencia='2026-04-17',
        prestador=Prestador(
            cnpj='53196577000187',
            inscricao_municipal='109984',
            razao_social='MAGG TECNOLOGIA DA INFORMACAO LTDA',
            telefone='38998534445',
            email='dmlmagal@gmail.com',
        ),
        tomador=Tomador(
            razao_social='Bellasoft LLC',
            email=None,
            logradouro='Union Street',
            numero='301',
            bairro='Central Business District',
            codigo_pais='US',
            codigo_end_postal='98101',
            cidade_exterior='Seattle',
            estado_exterior='Washington',
        ),
        servico=Servico(
            item_lista_servico='010101',
            codigo_tributacao_municipio='001',
            codigo_nbs='115022000',
            discriminacao='Criação\\Manutenção\\Correção de sistema proprietário.',
            codigo_municipio='3143302',
            valor_servicos=Decimal('5'),
            iss_retido=1,
        ),
    )


def init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nfse_emitidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_dps INTEGER NOT NULL UNIQUE,
                id_dps TEXT,
                chave_acesso TEXT,
                codigo_municipio TEXT NOT NULL,
                cnpj_prestador TEXT NOT NULL,
                serie TEXT NOT NULL,
                valor_servicos TEXT NOT NULL,
                resposta_json TEXT NOT NULL,
                emitida_em TEXT NOT NULL
            )
            """
        )
        conn.commit()


def proximo_numero_dps(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute('SELECT COALESCE(MAX(numero_dps), 0) + 1 FROM nfse_emitidas').fetchone()
    return int(row[0])


def registrar_nf_emitida(
    db_path: Path,
    numero_dps: int,
    data: RpsData,
    response_payload: dict,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO nfse_emitidas (
                numero_dps,
                id_dps,
                chave_acesso,
                codigo_municipio,
                cnpj_prestador,
                serie,
                valor_servicos,
                resposta_json,
                emitida_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                numero_dps,
                response_payload.get('idDps') or response_payload.get('idDPS'),
                response_payload.get('chaveAcesso'),
                data.servico.codigo_municipio,
                data.prestador.cnpj,
                data.serie,
                f'{data.servico.valor_servicos:.2f}',
                json.dumps(response_payload, ensure_ascii=True),
                datetime.now().isoformat(timespec='seconds'),
            ),
        )
        conn.commit()


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


def _response_json_or_fallback(response: requests.Response) -> dict:
    try:
        parsed = response.json()
        return parsed if isinstance(parsed, dict) else {'raw_response': response.text}
    except ValueError:
        return {'raw_response': response.text}


def _has_error_code(payload: dict, code: str) -> bool:
    erros = payload.get('erros')
    if not isinstance(erros, list):
        return False
    for err in erros:
        if isinstance(err, dict) and err.get('Codigo') == code:
            return True
    return False


def gerar_id_dps(data: RpsData) -> str:
    # Padrao observado no Emissor Nacional:
    # DPS + cLocEmi(7) + tpInscricaoPrest(1: 2=CNPJ) + inscricao(14) + serie(5) + numero(15)
    return (
        f'DPS{data.servico.codigo_municipio}'
        f'2'
        f'{data.prestador.cnpj}'
        f'{data.serie.zfill(5)}'
        f'{data.numero.zfill(15)}'
    )


def build_dps_xml(data: RpsData, ambiente: int, enviar_im_prestador: bool) -> tuple[bytes, str]:
    ET.register_namespace('', NAMESPACE_NFSE)
    dps = ET.Element(f'{{{NAMESPACE_NFSE}}}DPS', {'versao': VERSAO_DPS})
    inf_id = gerar_id_dps(data)
    inf = ET.SubElement(dps, 'infDPS', {'Id': inf_id})

    ET.SubElement(inf, 'tpAmb').text = str(ambiente)
    ET.SubElement(inf, 'dhEmi').text = data.data_emissao.isoformat()
    ET.SubElement(inf, 'verAplic').text = 'EmissorWeb_1.6.0.0'
    ET.SubElement(inf, 'serie').text = data.serie
    ET.SubElement(inf, 'nDPS').text = data.numero
    ET.SubElement(inf, 'dCompet').text = data.competencia
    ET.SubElement(inf, 'tpEmit').text = '1'
    ET.SubElement(inf, 'cLocEmi').text = data.servico.codigo_municipio

    prest = ET.SubElement(inf, 'prest')
    ET.SubElement(prest, 'CNPJ').text = data.prestador.cnpj
    if enviar_im_prestador and data.prestador.inscricao_municipal:
        ET.SubElement(prest, 'IM').text = data.prestador.inscricao_municipal
    if data.prestador.telefone:
        ET.SubElement(prest, 'fone').text = data.prestador.telefone
    if data.prestador.email:
        ET.SubElement(prest, 'email').text = data.prestador.email
    reg_trib = ET.SubElement(prest, 'regTrib')
    ET.SubElement(reg_trib, 'opSimpNac').text = '3'
    ET.SubElement(reg_trib, 'regApTribSN').text = '1'
    ET.SubElement(reg_trib, 'regEspTrib').text = '0'

    toma = ET.SubElement(inf, 'toma')
    ET.SubElement(toma, 'cNaoNIF').text = '1'
    ET.SubElement(toma, 'xNome').text = data.tomador.razao_social
    end = ET.SubElement(toma, 'end')
    end_ext = ET.SubElement(end, 'endExt')
    if data.tomador.codigo_pais:
        ET.SubElement(end_ext, 'cPais').text = data.tomador.codigo_pais
    if data.tomador.codigo_end_postal:
        ET.SubElement(end_ext, 'cEndPost').text = data.tomador.codigo_end_postal
    if data.tomador.cidade_exterior:
        ET.SubElement(end_ext, 'xCidade').text = data.tomador.cidade_exterior
    if data.tomador.estado_exterior:
        ET.SubElement(end_ext, 'xEstProvReg').text = data.tomador.estado_exterior
    ET.SubElement(end, 'xLgr').text = data.tomador.logradouro
    ET.SubElement(end, 'nro').text = data.tomador.numero
    ET.SubElement(end, 'xBairro').text = data.tomador.bairro

    serv = ET.SubElement(inf, 'serv')
    loc_prest = ET.SubElement(serv, 'locPrest')
    ET.SubElement(loc_prest, 'cLocPrestacao').text = data.servico.codigo_municipio
    c_serv = ET.SubElement(serv, 'cServ')
    ET.SubElement(c_serv, 'cTribNac').text = data.servico.item_lista_servico
    ET.SubElement(c_serv, 'cTribMun').text = data.servico.codigo_tributacao_municipio
    ET.SubElement(c_serv, 'xDescServ').text = data.servico.discriminacao
    if data.servico.codigo_nbs:
        ET.SubElement(c_serv, 'cNBS').text = data.servico.codigo_nbs
    com_ext = ET.SubElement(serv, 'comExt')
    ET.SubElement(com_ext, 'mdPrestacao').text = '4'
    ET.SubElement(com_ext, 'vincPrest').text = '0'
    ET.SubElement(com_ext, 'tpMoeda').text = '220'
    ET.SubElement(com_ext, 'vServMoeda').text = '1'
    ET.SubElement(com_ext, 'mecAFComexP').text = '01'
    ET.SubElement(com_ext, 'mecAFComexT').text = '01'
    ET.SubElement(com_ext, 'movTempBens').text = '1'
    ET.SubElement(com_ext, 'mdic').text = '0'

    valores = ET.SubElement(inf, 'valores')
    v_serv_prest = ET.SubElement(valores, 'vServPrest')
    ET.SubElement(v_serv_prest, 'vServ').text = f'{data.servico.valor_servicos:.2f}'
    trib = ET.SubElement(valores, 'trib')
    trib_mun = ET.SubElement(trib, 'tribMun')
    ET.SubElement(trib_mun, 'tribISSQN').text = '3'
    ET.SubElement(trib_mun, 'cPaisResult').text = 'US'
    ET.SubElement(trib_mun, 'tpRetISSQN').text = str(data.servico.iss_retido)
    trib_fed = ET.SubElement(trib, 'tribFed')
    piscofins = ET.SubElement(trib_fed, 'piscofins')
    ET.SubElement(piscofins, 'CST').text = '00'
    tot_trib = ET.SubElement(trib, 'totTrib')
    ET.SubElement(tot_trib, 'pTotTribSN').text = '6.00'

    xml_bytes = ET.tostring(dps, encoding='utf-8', xml_declaration=True)
    return xml_bytes, inf_id


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


def _cert_and_key_from_pfx(pfx_path: Path, pfx_password: str) -> tuple[str, str]:
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

    cert_path, key_path = _cert_and_key_from_pfx(pfx_path, pfx_password)
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Assina DPS (Emissor Nacional) e envia para endpoint de homologacao.'
    )
    parser.add_argument(
        '--db-path', type=Path, default=Path('nfse.db'), help='Banco SQLite das NFS-e emitidas.'
    )
    parser.add_argument(
        '--emissoes-dir',
        type=Path,
        default=Path('emissoes'),
        help='Diretorio base para salvar XML de retorno (organizado por ano/mes).',
    )
    parser.add_argument('--pfx', type=Path, default=Path('1009580140.pfx'), help='Arquivo PFX.')
    parser.add_argument('--pfx-password', required=True, help='Senha do PFX.')
    parser.add_argument(
        '--ambiente',
        choices=tuple(ENVIRONMENTS.keys()),
        default='homologacao',
        help='Seleciona ambiente e serie padrao para emissao.',
    )
    parser.add_argument('--endpoint', help='Endpoint de envio. Sobrescreve o endpoint do ambiente.')
    parser.add_argument('--serie', help='Serie da DPS. Sobrescreve a serie padrao do ambiente.')
    parser.add_argument('--timeout', type=int, default=60, help='Timeout HTTP em segundos.')
    parser.add_argument(
        '--max-tentativas', type=int, default=10, help='Tentativas para contornar duplicidade de numero DPS.'
    )
    parser.add_argument('--insecure', action='store_true', help='Nao valida certificado TLS do servidor.')
    parser.add_argument(
        '--somente-assinar',
        action='store_true',
        help='Gera e assina o DPS sem enviar.',
    )
    args = parser.parse_args()

    env_cfg = ENVIRONMENTS[args.ambiente]
    endpoint = args.endpoint or str(env_cfg['endpoint'])
    ambiente_codigo = int(env_cfg['ambiente'])
    serie = args.serie or str(env_cfg['serie'])
    enviar_im_prestador = bool(int(env_cfg.get('enviar_im_prestador', 0)))

    init_db(args.db_path)
    numero_dps = proximo_numero_dps(args.db_path)
    for tentativa in range(1, args.max_tentativas + 1):
        data = dados_fixos_nfse(numero_dps=numero_dps, serie=serie)
        xml_dps, reference_id = build_dps_xml(
            data=data,
            ambiente=ambiente_codigo,
            enviar_im_prestador=enviar_im_prestador,
        )
        signed_xml = sign_dps_xml(
            xml_bytes=xml_dps,
            reference_id=reference_id,
            pfx_path=args.pfx,
            pfx_password=args.pfx_password,
        )
        print(f'DPS assinado em memoria (numero={numero_dps}, tentativa={tentativa}).')

        if args.somente_assinar:
            print('Envio ignorado (--somente-assinar).')
            return 0

        response = send_signed_dps(
            endpoint=endpoint,
            signed_xml=signed_xml,
            pfx_path=args.pfx,
            pfx_password=args.pfx_password,
            timeout=args.timeout,
            verify_ssl=not args.insecure,
        )
        print(f'HTTP {response.status_code}')
        print(response.text)

        payload = _response_json_or_fallback(response)
        if response.ok:
            xml_salvo = salvar_xml_retorno_nfse(payload, args.emissoes_dir)
            registrar_nf_emitida(args.db_path, numero_dps=numero_dps, data=data, response_payload=payload)
            print(f'NF registrada no banco: {args.db_path} (numero_dps={numero_dps})')
            if xml_salvo is not None:
                print(f'XML de retorno salvo em: {xml_salvo}')
            else:
                print('Resposta nao trouxe nfseXmlGZipB64; nenhum XML salvo.')
            return 0

        if _has_error_code(payload, 'E0014'):
            numero_dps += 1
            continue

        return 1

    print('Falha: excedeu maximo de tentativas para numero da DPS.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
