from __future__ import annotations

from typing import Final

from .models import Prestador, Tomador

DEFAULT_PRESTADOR: Final[Prestador] = Prestador(
    cnpj='53196577000187',
    inscricao_municipal='109984',
    razao_social='MAGG TECNOLOGIA DA INFORMACAO LTDA',
    telefone='38998534445',
    email='dmlmagal@gmail.com',
)

DEFAULT_TOMADOR: Final[Tomador] = Tomador(
    razao_social='Bellasoft LLC',
    email=None,
    logradouro='Union Street',
    numero='301',
    bairro='Central Business District',
    codigo_pais='US',
    codigo_end_postal='98101',
    cidade_exterior='Seattle',
    estado_exterior='Washington',
)

NAMESPACE_NFSE: Final[str] = 'http://www.sped.fazenda.gov.br/nfse'
VERSAO_DPS: Final[str] = '1.01'
DEFAULT_SERIE_DPS: Final[str] = '900'
ENVIRONMENTS: Final[dict[str, dict[str, int | str | bool]]] = {
    'homologacao': {
        'endpoint': 'https://sefin.producaorestrita.nfse.gov.br/SefinNacional/nfse',
        'ambiente': 2,
        'enviar_im_prestador': False,
    },
    'producao': {
        'endpoint': 'https://sefin.nfse.gov.br/SefinNacional/nfse',
        'ambiente': 1,
        'enviar_im_prestador': True,
    },
}
