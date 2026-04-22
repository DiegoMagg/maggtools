from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

import streamlit as st

from nfse import (
    DEFAULT_SERIE_DPS,
    ENVIRONMENTS,
    Prestador,
    RpsData,
    Tomador,
    _has_error_code,
    _response_json_or_fallback,
    build_dps_xml,
    dados_fixos_nfse,
    init_db,
    listar_prestadores,
    listar_tomadores,
    proximo_numero_dps,
    registrar_nf_emitida,
    salvar_xml_retorno_nfse,
    send_signed_dps,
    sign_dps_xml,
)


def _build_preview_data(
    db_path: Path,
    serie: str,
    data_emissao: datetime,
    valor_reais: Decimal,
    valor_dolar: Decimal,
    prestador: Prestador,
    tomador: Tomador,
) -> tuple[int, RpsData]:
    init_db(db_path)
    numero_dps = proximo_numero_dps(db_path)
    data = dados_fixos_nfse(
        numero_dps=numero_dps,
        serie=serie,
        data_emissao=data_emissao,
        valor_servicos=valor_reais,
        valor_moeda=valor_dolar,
        prestador=prestador,
        tomador=tomador,
    )
    return numero_dps, data


def _open_nf_confirm_modal(
    *,
    preview_numero: int,
    preview_data: object,
    ambiente: str,
    endpoint: str,
    data_emissao_texto: str,
    valor_reais_texto: str,
    valor_dolar_texto: str,
) -> None:
    @st.dialog('Confirmar dados da NFS-e')
    def _confirm_dialog() -> None:
        st.write('Revise as informacoes abaixo antes de gerar a NFS-e:')
        st.write(f'Numero DPS previsto: `{preview_numero}`')
        st.write(f'Ambiente: `{ambiente}`')
        st.write(f'Endpoint: `{endpoint}`')
        st.write(f'Data emissao: `{data_emissao_texto}`')
        st.write(f'Valor em reais (vServ): `{valor_reais_texto}`')
        st.write(f'Valor em dolar (vServMoeda): `{valor_dolar_texto}`')

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('#### Emissor (Prestador)')
            st.json(
                {
                    'cnpj': preview_data.prestador.cnpj,
                    'inscricao_municipal': preview_data.prestador.inscricao_municipal,
                    'razao_social': preview_data.prestador.razao_social,
                    'telefone': preview_data.prestador.telefone,
                    'email': preview_data.prestador.email,
                }
            )
        with col2:
            st.markdown('#### Tomador')
            st.json(
                {
                    'razao_social': preview_data.tomador.razao_social,
                    'email': preview_data.tomador.email,
                    'logradouro': preview_data.tomador.logradouro,
                    'numero': preview_data.tomador.numero,
                    'bairro': preview_data.tomador.bairro,
                    'codigo_pais': preview_data.tomador.codigo_pais,
                    'codigo_end_postal': preview_data.tomador.codigo_end_postal,
                    'cidade_exterior': preview_data.tomador.cidade_exterior,
                    'estado_exterior': preview_data.tomador.estado_exterior,
                }
            )

        if st.button(
            'Confirmar e gerar NFS-e',
            type='primary',
            key='confirmar_modal_emitir_nfse',
        ):
            st.session_state['executar_emissao'] = True
            st.rerun()

    _confirm_dialog()


def main() -> None:
    st.set_page_config(page_title='Emissor NFS-e', page_icon='🧾', layout='wide')
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 980px;
                margin-left: auto;
                margin-right: auto;
            }
            div[data-testid="stDialog"] div[role="dialog"] {
                width: 96vw !important;
                max-width: 1280px !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title('Emissor NFS-e Nacional')
    st.caption('Preencha os dados, confira emissor/tomador e gere a NFS-e.')

    col1, col2 = st.columns(2)

    with col1:
        ambiente = st.selectbox('Ambiente', options=list(ENVIRONMENTS.keys()), index=0)
        endpoint_custom = st.text_input('Endpoint (opcional)')
        serie = st.text_input('Serie DPS', value=DEFAULT_SERIE_DPS)
        agora_local = datetime.now().astimezone()
        data_col, hora_col, minuto_col = st.columns([2, 1, 1])
        with data_col:
            data_emissao_date = st.date_input('Data de emissão *', value=agora_local.date())
        with hora_col:
            hora_emissao = st.selectbox('Hora *', options=list(range(24)), index=agora_local.hour)
        with minuto_col:
            minuto_emissao = st.selectbox('Minuto *', options=list(range(60)), index=agora_local.minute)
        valor_reais_texto = st.text_input('Valor em reais *', value='')
        valor_dolar_texto = st.text_input('Valor em dólar *', value='')

    with col2:
        pfx_path_texto = st.text_input('Arquivo PFX *', value='1009580140.pfx')
        pfx_password = st.text_input('Senha do PFX *', type='password')
        db_path_texto = st.text_input('Banco SQLite', value='nfse.db')
        emissoes_dir_texto = st.text_input('Diretório de emissões', value='emissoes')
        timeout = st.number_input('Timeout (segundos)', min_value=5, max_value=300, value=60, step=5)
        max_tentativas = st.number_input(
            'Max tentativas (E0014)', min_value=1, max_value=100, value=10, step=1
        )

    errors: list[str] = []
    data_emissao: datetime | None = None
    valor_reais: Decimal | None = None
    valor_dolar: Decimal | None = None

    try:
        tzinfo_local = datetime.now().astimezone().tzinfo
        data_emissao_time = time(hour=int(hora_emissao), minute=int(minuto_emissao), second=0)
        data_emissao = datetime.combine(data_emissao_date, data_emissao_time, tzinfo=tzinfo_local)
    except Exception:
        errors.append('`Data emissao` invalida.')

    required_missing = (
        not valor_reais_texto.strip() or not valor_dolar_texto.strip() or not pfx_password.strip()
    )

    if valor_reais_texto.strip():
        try:
            valor_reais = Decimal(valor_reais_texto.strip())
        except Exception:
            errors.append('`Valor reais` invalido.')

    if valor_dolar_texto.strip():
        try:
            valor_dolar = Decimal(valor_dolar_texto.strip())
        except Exception:
            errors.append('`Valor dolar` invalido.')

    db_path = Path(db_path_texto.strip())
    pfx_path = Path(pfx_path_texto.strip())
    emissoes_dir = Path(emissoes_dir_texto.strip())
    init_db(db_path)

    prestadores = listar_prestadores(db_path)
    tomadores = listar_tomadores(db_path)

    selected_prestador: Prestador | None = None
    selected_tomador: Tomador | None = None

    if prestadores:
        prestador_options = {f'{p.razao_social} ({p.cnpj})': p for p in prestadores}
        selected_prestador = st.selectbox('Prestador', options=list(prestador_options.keys()), index=0)
        selected_prestador = prestador_options[selected_prestador]
    else:
        errors.append('Nenhum prestador cadastrado na tabela `prestadores`.')

    if tomadores:
        tomador_options = {
            (
                f'{t.razao_social} - {t.logradouro}, {t.numero} '
                f'({t.cidade_exterior or "-"} / {t.codigo_pais or "-"})'
            ): t
            for t in tomadores
        }
        selected_tomador = st.selectbox('Tomador', options=list(tomador_options.keys()), index=0)
        selected_tomador = tomador_options[selected_tomador]
    else:
        errors.append('Nenhum tomador cadastrado na tabela `tomadores`.')

    insecure = st.checkbox('Não validar certificado TLS')
    somente_assinar = st.checkbox('Somente assinar (não enviar)')
    st.caption('Campos com * são necessários.')

    if not pfx_path.exists():
        errors.append(f'Arquivo PFX não encontrado: `{pfx_path}`')

    preview_numero: int | None = None
    preview_data = None
    if (
        not errors
        and data_emissao is not None
        and valor_reais is not None
        and valor_dolar is not None
        and selected_prestador is not None
        and selected_tomador is not None
    ):
        try:
            preview_numero, preview_data = _build_preview_data(
                db_path=db_path,
                serie=serie.strip(),
                data_emissao=data_emissao,
                valor_reais=valor_reais,
                valor_dolar=valor_dolar,
                prestador=selected_prestador,
                tomador=selected_tomador,
            )
        except Exception as exc:
            errors.append(f'Falha ao preparar pre-visualizacao: {exc}')

    if errors:
        for err in errors:
            st.error(err)

    if 'executar_emissao' not in st.session_state:
        st.session_state['executar_emissao'] = False

    gerar = st.button('Abrir confirmacao da NFS-e', type='primary', disabled=bool(errors) or required_missing)

    if gerar and preview_data is not None:
        endpoint = endpoint_custom.strip() or str(ENVIRONMENTS[ambiente]['endpoint'])
        _open_nf_confirm_modal(
            preview_numero=int(preview_numero),
            preview_data=preview_data,
            ambiente=ambiente,
            endpoint=endpoint,
            data_emissao_texto=data_emissao.isoformat(timespec='seconds') if data_emissao else '',
            valor_reais_texto=valor_reais_texto.strip(),
            valor_dolar_texto=valor_dolar_texto.strip(),
        )

    if not st.session_state.get('executar_emissao', False):
        return
    st.session_state['executar_emissao'] = False

    if errors:
        st.warning('Corrija os erros antes de gerar a NFS-e.')
        return

    if preview_data is None:
        st.error('Nao foi possivel montar os dados da emissao.')
        return

    env_cfg = ENVIRONMENTS[ambiente]
    endpoint = endpoint_custom.strip() or str(env_cfg['endpoint'])
    ambiente_codigo = int(env_cfg['ambiente'])
    enviar_im_prestador = bool(int(env_cfg.get('enviar_im_prestador', 0)))

    numero_dps = int(preview_numero)
    with st.status('Processando emissao...', expanded=True) as status:
        for tentativa in range(1, int(max_tentativas) + 1):
            data = dados_fixos_nfse(
                numero_dps=numero_dps,
                serie=serie.strip(),
                data_emissao=data_emissao,
                valor_servicos=valor_reais,
                valor_moeda=valor_dolar,
                prestador=selected_prestador,
                tomador=selected_tomador,
            )
            xml_dps, reference_id = build_dps_xml(
                data=data,
                ambiente=ambiente_codigo,
                enviar_im_prestador=enviar_im_prestador,
            )
            # Streamlit nao deve quebrar em caso de senha/PFX invalido.
            # A biblioteca levanta ValueError para senha incorreta ou arquivo PKCS12 invalido.
            try:
                signed_xml = sign_dps_xml(
                    xml_bytes=xml_dps,
                    reference_id=reference_id,
                    pfx_path=pfx_path,
                    pfx_password=pfx_password,
                )
            except ValueError as exc:
                status.update(label='Falha ao assinar DPS.', state='error')
                st.error(f'Erro ao ler PFX: {exc}')
                st.info('Verifique se o arquivo PFX esta correto e se a senha informada confere.')
                return
            except Exception as exc:
                status.update(label='Falha ao assinar DPS.', state='error')
                st.error(f'Erro inesperado na assinatura: {exc}')
                return
            st.write(f'DPS assinado (numero={numero_dps}, tentativa={tentativa}).')

            if somente_assinar:
                status.update(label='DPS assinado com sucesso.', state='complete')
                st.success('Assinatura concluida (envio ignorado).')
                return

            response = send_signed_dps(
                endpoint=endpoint,
                signed_xml=signed_xml,
                pfx_path=pfx_path,
                pfx_password=pfx_password,
                timeout=int(timeout),
                verify_ssl=not insecure,
            )
            payload = _response_json_or_fallback(response)
            st.write(f'HTTP {response.status_code}')

            if response.ok:
                xml_salvo = salvar_xml_retorno_nfse(payload, emissoes_dir)
                registrar_nf_emitida(db_path, numero_dps=numero_dps, data=data, response_payload=payload)
                status.update(label='NFS-e emitida com sucesso.', state='complete')
                st.success(f'NFS-e registrada no banco (numero_dps={numero_dps}).')
                if xml_salvo is not None:
                    st.info(f'XML salvo em: `{xml_salvo}`')
                st.json(payload)
                return

            st.error('Falha na resposta da API.')
            st.json(payload)
            if _has_error_code(payload, 'E0014'):
                numero_dps += 1
                continue

            status.update(label='Falha ao emitir NFS-e.', state='error')
            return

    st.error('Falha: excedeu o maximo de tentativas para numero da DPS.')


if __name__ == '__main__':
    main()
