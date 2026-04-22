from __future__ import annotations

import argparse
from pathlib import Path

from nfse.application.emitir_nfse import parse_datetime, parse_decimal
from nfse.domain.constants import DEFAULT_SERIE_DPS, ENVIRONMENTS
from nfse.domain.services import dados_fixos_nfse
from nfse.infrastructure.http.nfse_client import has_error_code, response_json_or_fallback, send_signed_dps
from nfse.infrastructure.persistence.sqlite_repo import (
    init_db,
    proximo_numero_dps,
    registrar_nf_emitida,
)
from nfse.infrastructure.security.signer import sign_dps_xml
from nfse.infrastructure.storage.xml_store import salvar_xml_retorno_nfse
from nfse.infrastructure.xml.dps_builder import build_dps_xml


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
    parser.add_argument('--serie', default=DEFAULT_SERIE_DPS, help='Serie da DPS. Padrao: 900.')
    parser.add_argument(
        '--data-emissao',
        type=parse_datetime,
        required=True,
        help='Data/hora de emissao em ISO 8601 (ex.: 2026-04-22T13:46:01-03:00).',
    )
    parser.add_argument(
        '--valor-reais',
        type=parse_decimal,
        required=True,
        help='Valor de servicos (decimal) para vServ.',
    )
    parser.add_argument(
        '--valor-dolar',
        type=parse_decimal,
        required=True,
        help='Valor em moeda estrangeira (decimal) para vServMoeda.',
    )
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
    enviar_im_prestador = bool(int(env_cfg.get('enviar_im_prestador', 0)))

    init_db(args.db_path)
    numero_dps = proximo_numero_dps(args.db_path)
    for tentativa in range(1, args.max_tentativas + 1):
        data = dados_fixos_nfse(
            numero_dps=numero_dps,
            serie=args.serie,
            data_emissao=args.data_emissao,
            valor_servicos=args.valor_reais,
            valor_moeda=args.valor_dolar,
        )
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

        payload = response_json_or_fallback(response)
        if response.ok:
            xml_salvo = salvar_xml_retorno_nfse(payload, args.emissoes_dir)
            registrar_nf_emitida(
                args.db_path,
                numero_dps=numero_dps,
                ambiente=args.ambiente,
                data=data,
                response_payload=payload,
            )
            print(f'NF registrada no banco: {args.db_path} (numero_dps={numero_dps})')
            if xml_salvo is not None:
                print(f'XML de retorno salvo em: {xml_salvo}')
            else:
                print('Resposta nao trouxe nfseXmlGZipB64; nenhum XML salvo.')
            return 0

        if has_error_code(payload, 'E0014'):
            numero_dps += 1
            continue

        return 1

    print('Falha: excedeu maximo de tentativas para numero da DPS.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
