from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .constants import DEFAULT_TOMADOR
from .models import Prestador, RpsData, Servico, Tomador


def dados_fixos_nfse(
    numero_dps: int,
    serie: str,
    data_emissao: datetime,
    valor_servicos: Decimal,
    valor_moeda: Decimal,
    prestador: Prestador,
    tomador: Tomador = DEFAULT_TOMADOR,
) -> RpsData:
    competencia = data_emissao.date().isoformat()
    return RpsData(
        numero=str(numero_dps),
        serie=serie,
        data_emissao=data_emissao,
        competencia=competencia,
        prestador=prestador,
        tomador=tomador,
        servico=Servico(
            item_lista_servico='010101',
            codigo_tributacao_municipio='001',
            codigo_nbs='115022000',
            discriminacao='Criação\\Manutenção\\Correção de sistema proprietário.',
            codigo_municipio='3143302',
            valor_servicos=valor_servicos,
            valor_moeda=valor_moeda,
            iss_retido=1,
        ),
    )


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
