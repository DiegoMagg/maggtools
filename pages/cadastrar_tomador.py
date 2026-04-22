from __future__ import annotations

from pathlib import Path

import streamlit as st

from nfse import Tomador, cadastrar_tomador, init_db, listar_tomadores
from page_layout import render_page

PAISES_OPTIONS = [
    'Selecione...',
    'Afeganistao',
    'Africa do Sul',
    'Aland, Ilhas',
    'Albania, Republica da',
    'Alemanha',
    'Andorra',
    'Angola',
    'Anguilla',
    'Antartica',
    'Antigua e Barbuda',
    'Arabia Saudita',
    'Argelia',
    'Argentina',
    'Armenia, Republica da',
    'Aruba',
    'Australia',
    'Austria',
    'Azerbaijao, Republica do',
    'Bahamas, Ilhas',
    'Bahrein, Ilhas',
    'Bangladesh',
    'Barbados',
    'Belarus, Republica da',
    'Belgica',
    'Belize',
    'Benim',
    'Bermudas',
    'Bolivia',
    'Bonaire, Santo Eustaquio e Saba',
    'Bosnia-Herzegovina, Republica da',
    'Botsuana',
    'Bouvet, Ilha',
    'Brunei',
    'Bulgaria, Republica da',
    'Burkina Faso',
    'Burundi',
    'Butao',
    'Cabo Verde, Republica de',
    'Camaroes',
    'Camboja',
    'Canada',
    'Catar',
    'Cayman, Ilhas',
    'Cazaquistao, Republica do',
    'Chade',
    'Chile',
    'China, Republica Popular',
    'Chipre',
    'Christmas, Ilha',
    'Cingapura',
    'Cocos(Keeling), Ilhas',
    'Colombia',
    'Comores, Ilhas',
    'Congo',
    'Congo, Republica Democratica do',
    'Cook, Ilhas',
    'Coreia (do Norte), Rep. Pop. Democratica da',
    'Coreia (do Sul), Republica da',
    'Costa do Marfim',
    'Costa Rica',
    'Croacia, Republica da',
    'Cuba',
    'Curacao',
    'Dinamarca',
    'Djibuti',
    'Dominica, Ilha',
    'Egito',
    'El Salvador',
    'Emirados Arabes Unidos',
    'Equador',
    'Eritreia',
    'Eslovaca, Republica',
    'Eslovenia, Republica da',
    'Espanha',
    'Estados Unidos',
    'Estonia, Republica da',
    'Etiopia',
    'Falkland (Ilhas Malvinas)',
    'Feroe, Ilhas',
    'Fiji',
    'Filipinas',
    'Finlandia',
    'Formosa (Taiwan)',
    'Franca',
    'Gabao',
    'Gambia',
    'Gana',
    'Georgia, Republica da',
    'Gibraltar',
    'Granada',
    'Grecia',
    'Groenlandia',
    'Guadalupe',
    'Guam',
    'Guatemala',
    'Guernsey',
    'Guiana Francesa',
    'Guiana',
    'Guine',
    'Guine-Bissau',
    'Guine-Equatorial',
    'Haiti',
    'Honduras',
    'Hong Kong',
    'Hungria, Republica da',
    'Iemen',
    'Ilha Heard e Ilhas McDonald',
    'Ilhas Georgia do Sul e Sandwich do Sul',
    'India',
    'Indonesia',
    'Ira, Republica Islamica do',
    'Iraque',
    'Irlanda',
    'Islandia',
    'Israel',
    'Italia',
    'Jamaica',
    'Japao',
    'Jersey',
    'Jordania',
    'Kiribati',
    'Kuwait',
    'Laos, Rep. Pop. Democratica do',
    'Lesoto',
    'Letonia, Republica da',
    'Libano',
    'Liberia',
    'Libia',
    'Liechtenstein',
    'Lituania, Republica da',
    'Luxemburgo',
    'Macau',
    'Macedonia, Ant. Rep. Iugoslava',
    'Madagascar',
    'Malasia',
    'Malavi',
    'Maldivas',
    'Mali',
    'Malta',
    'Man, Ilha de',
    'Marianas do Norte',
    'Marrocos',
    'Marshall, Ilhas',
    'Martinica',
    'Mauricio',
    'Mauritania',
    'Mayotte',
    'Mexico',
    'Micronesia',
    'Mocambique',
    'Moldavia, Republica da',
    'Monaco',
    'Mongolia',
    'Montenegro',
    'Montserrat, Ilhas',
    'Myanmar (Birmania)',
    'Namibia',
    'Nauru',
    'Nepal',
    'Nicaragua',
    'Niger',
    'Nigeria',
    'Niue, Ilha',
    'Norfolk, Ilha',
    'Noruega',
    'Nova Caledonia',
    'Nova Zelandia',
    'Oma',
    'Pacifico, Ilhas do (Possessao dos EUA)',
    'Paises Baixos (Holanda)',
    'Palau',
    'Palestina',
    'Panama',
    'Papua Nova Guine',
    'Paquistao',
    'Paraguai',
    'Peru',
    'Pitcairn, Ilha De',
    'Polinesia Francesa',
    'Polonia, Republica da',
    'Porto Rico',
    'Portugal',
    'Quenia',
    'Quirguiz, Republica da',
    'Reino Unido',
    'Republica Centro-Africana',
    'Republica Dominicana',
    'Reuniao, Ilha',
    'Romenia',
    'Ruanda',
    'Russia, Federacao da',
    'Saara Ocidental',
    'Salomao, Ilhas',
    'Samoa Americana',
    'Samoa',
    'San Marino',
    'Santa Helena',
    'Santa Lucia',
    'Sao Bartolomeu',
    'Sao Cristovao e Neves, Ilhas',
    'Sao Martinho (Parte Francesa)',
    'Sao Martinho (Parte Holandesa)',
    'Sao Pedro e Miquelon',
    'Sao Tome e Principe, Ilhas',
    'Sao Vicente e Granadinas',
    'Senegal',
    'Serra Leoa',
    'Servia',
    'Seychelles',
    'Siria, Republica Arabe da',
    'Somalia',
    'Sri Lanka',
    'Suazilandia',
    'Sudao do Sul',
    'Sudao',
    'Suecia',
    'Suica',
    'Suriname',
    'Svalbard e Jan Mayen',
    'Tadjiquistao, Republica do',
    'Tailandia',
    'Tanzania, Rep. Unida da',
    'Tcheca, Republica',
    'Terras Austrais e Antarticas Francesas',
    'Territorio Britanico no Oceano Indico',
    'Timor Leste',
    'Togo',
    'Tonga',
    'Toquelau, Ilhas',
    'Trinidad e Tobago',
    'Tunisia',
    'Turcas e Caicos, Ilhas',
    'Turcomenistao, Republica do',
    'Turquia',
    'Tuvalu',
    'Ucrania',
    'Uganda',
    'Uruguai',
    'Uzbequistao, Republica do',
    'Vanuatu',
    'Vaticano, Est. da Cidade do',
    'Venezuela',
    'Vietna',
    'Virgens, Ilhas (Britanicas)',
    'Virgens, Ilhas (E.U.A.)',
    'Wallis e Futuna, Ilhas',
    'Zambia',
    'Zimbabue',
]


def _none_if_blank(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def main() -> None:
    st.set_page_config(page_title='Cadastrar Tomador', page_icon='👤', layout='wide')
    db_path = Path('nfse.db')
    init_db(db_path)
    with render_page('Cadastrar tomador', 'Cadastre novos tomadores para usar na emissão da NFS-e.'):
        with st.form('form_cadastro_tomador', clear_on_submit=True, border=False):
            razao_social = st.text_input('Nome/Razão Social *')

            contato_col1, contato_col2 = st.columns(2)
            with contato_col1:
                telefone = st.text_input('Telefone')
            with contato_col2:
                email = st.text_input('E-mail')

            endereco_col1, endereco_col2 = st.columns([2, 1])
            with endereco_col1:
                logradouro = st.text_input('Logradouro *')
            with endereco_col2:
                numero = st.text_input('Número *')

            linha_col1, linha_col2, linha_col3 = st.columns(3)
            with linha_col1:
                complemento = st.text_input('Complemento')
            with linha_col2:
                bairro = st.text_input('Bairro *')
            with linha_col3:
                cidade_exterior = st.text_input('Cidade *')

            fim_col1, fim_col2, fim_col3 = st.columns(3)
            with fim_col1:
                codigo_end_postal = st.text_input('Código de Endereçamento Postal *')
            with fim_col2:
                estado_exterior = st.text_input('Estado, província ou região *')
            with fim_col3:
                codigo_pais = st.selectbox('País *', options=PAISES_OPTIONS, index=0)

            submitted = st.form_submit_button('Salvar tomador', type='primary')

    if submitted:
        errors: list[str] = []
        if not razao_social.strip():
            errors.append('`Razão social` é obrigatória.')
        if not logradouro.strip():
            errors.append('`Logradouro` é obrigatório.')
        if not numero.strip():
            errors.append('`Número` é obrigatório.')
        if not bairro.strip():
            errors.append('`Bairro` é obrigatório.')
        if not cidade_exterior.strip():
            errors.append('`Cidade` é obrigatória.')
        if not codigo_end_postal.strip():
            errors.append('`Código de Endereçamento Postal` é obrigatório.')
        if not estado_exterior.strip():
            errors.append('`Estado, província ou região` é obrigatório.')
        if codigo_pais == 'Selecione...':
            errors.append('`País` é obrigatório.')

        if errors:
            for err in errors:
                st.error(err)
        else:
            _ = telefone
            logradouro_final = logradouro.strip()
            if complemento.strip():
                logradouro_final = f'{logradouro_final}, {complemento.strip()}'

            tomador = Tomador(
                razao_social=razao_social.strip(),
                email=_none_if_blank(email),
                logradouro=logradouro_final,
                numero=numero.strip(),
                bairro=bairro.strip(),
                codigo_pais=_none_if_blank(codigo_pais),
                codigo_end_postal=_none_if_blank(codigo_end_postal),
                cidade_exterior=_none_if_blank(cidade_exterior),
                estado_exterior=_none_if_blank(estado_exterior),
            )
            inserted = cadastrar_tomador(db_path, tomador)
            if inserted:
                st.success('Tomador cadastrado com sucesso.')
            else:
                st.warning('Já existe um tomador com a mesma razão social, logradouro e número.')

    st.markdown('### Tomadores cadastrados')
    tomadores = listar_tomadores(db_path)
    if not tomadores:
        st.info('Nenhum tomador cadastrado.')
        return

    st.dataframe(
        [
            {
                'razao_social': t.razao_social,
                'email': t.email,
                'logradouro': t.logradouro,
                'numero': t.numero,
                'bairro': t.bairro,
                'codigo_pais': t.codigo_pais,
                'codigo_end_postal': t.codigo_end_postal,
                'cidade_exterior': t.cidade_exterior,
                'estado_exterior': t.estado_exterior,
            }
            for t in tomadores
        ],
        width='stretch',
        hide_index=True,
    )


if __name__ == '__main__':
    main()
