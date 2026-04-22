from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


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
    valor_moeda: Decimal
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
