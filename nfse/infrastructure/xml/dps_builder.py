from __future__ import annotations

from xml.etree import ElementTree as ET

from nfse.domain.constants import NAMESPACE_NFSE, VERSAO_DPS
from nfse.domain.models import RpsData
from nfse.domain.services import gerar_id_dps


def build_dps_xml(data: RpsData, ambiente: int, enviar_im_prestador: bool) -> tuple[bytes, str]:
    ET.register_namespace('', NAMESPACE_NFSE)
    dps = ET.Element(f'{{{NAMESPACE_NFSE}}}DPS', {'versao': VERSAO_DPS})
    inf_id = gerar_id_dps(data)
    inf = ET.SubElement(dps, 'infDPS', {'Id': inf_id})

    ET.SubElement(inf, 'tpAmb').text = str(ambiente)
    ET.SubElement(inf, 'dhEmi').text = data.data_emissao.isoformat()
    ET.SubElement(inf, 'verAplic').text = 'MaggDevNFSe_1.0.0'
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
    ET.SubElement(com_ext, 'vServMoeda').text = f'{data.servico.valor_moeda:.2f}'
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
