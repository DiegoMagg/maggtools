from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import streamlit as st

from nfse import init_db
from page_layout import render_page
from ui_config import config_db_path, init_config_state


def _to_decimal(value: str) -> Decimal:
    raw = str(value or '').strip().replace(',', '.')
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def main() -> None:
    st.set_page_config(page_title='Dashboard', page_icon='📊', layout='wide')
    init_config_state()

    with render_page(
        'Dashboard NFS-e', 'Panorama em tempo real de emissão, cancelamento e volume financeiro.'
    ):
        db_path = config_db_path()
        init_db(db_path)
        ambiente = str(st.session_state.get('config_ambiente', 'producao')).strip().lower()

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            totais = conn.execute(
                """
                SELECT
                    COUNT(1) AS total_notas,
                    COALESCE(SUM(CASE WHEN cancelada = 0 THEN 1 ELSE 0 END), 0) AS total_ativas,
                    COALESCE(SUM(CASE WHEN cancelada = 1 THEN 1 ELSE 0 END), 0) AS total_canceladas,
                    COALESCE(SUM(CAST(valor_servicos AS REAL)), 0) AS valor_total
                FROM nfse_emitidas
                WHERE ambiente = ?
                """,
                (ambiente,),
            ).fetchone()
            por_mes = conn.execute(
                """
                SELECT
                    substr(emitida_em, 1, 7) AS mes,
                    COALESCE(SUM(CAST(valor_servicos AS REAL)), 0) AS valor_total_mes
                FROM nfse_emitidas
                WHERE emitida_em >= ?
                  AND ambiente = ?
                GROUP BY substr(emitida_em, 1, 7)
                ORDER BY mes ASC
                """,
                ((date.today() - timedelta(days=365)).isoformat(), ambiente),
            ).fetchall()
            ultimas = conn.execute(
                """
                SELECT
                    id,
                    numero_dps,
                    ambiente,
                    COALESCE(chave_acesso, '') AS chave_acesso,
                    COALESCE(cnpj_prestador, '') AS cnpj_prestador,
                    COALESCE(valor_servicos, '0') AS valor_servicos,
                    COALESCE(cancelada, 0) AS cancelada,
                    emitida_em
                FROM nfse_emitidas
                WHERE ambiente = ?
                ORDER BY id DESC
                LIMIT 8
                """,
                (ambiente,),
            ).fetchall()

        total_notas = int(totais[0] or 0)
        total_ativas = int(totais[1] or 0)
        total_canceladas = int(totais[2] or 0)
        valor_total = Decimal(str(totais[3] or 0))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Total de notas', f'{total_notas}')
        c2.metric('Ativas', f'{total_ativas}')
        c3.metric('Canceladas', f'{total_canceladas}')
        c4.metric(
            'Valor total (R$)', f'{valor_total:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        )

        st.markdown('---')
        dist_col, evo_col = st.columns([1, 2])

        with dist_col:
            st.markdown('#### Saúde do faturamento')
            ticket_medio = (valor_total / total_notas) if total_notas else Decimal('0')
            percentual_canceladas = (total_canceladas / total_notas * 100) if total_notas else 0
            st.write(
                f'- Ticket médio: `R$ {ticket_medio:,.2f}`'.replace(',', 'X')
                .replace('.', ',')
                .replace('X', '.')
            )
            st.write(f'- Taxa de cancelamento: `{percentual_canceladas:.1f}%`')

        with evo_col:
            st.markdown('#### Valor emitido por mês (últimos 12 meses)')
            if por_mes:
                grafico = {str(mes): float(valor or 0) for mes, valor in por_mes if float(valor or 0) > 0}
                if grafico:
                    st.area_chart(grafico, height=260)
                else:
                    st.info('Sem meses com valor positivo para exibir no período.')
            else:
                st.info('Sem emissões no período selecionado.')

            st.markdown('#### Últimas notas registradas')
            if ultimas:
                dados = []
                for row in ultimas:
                    dados.append(
                        {
                            'ID': int(row['id']),
                            'DPS': int(row['numero_dps']),
                            'Chave de acesso': str(row['chave_acesso']),
                            'CNPJ': str(row['cnpj_prestador']),
                            'Valor': f"R$ {_to_decimal(str(row['valor_servicos'])):,.2f}".replace(',', 'X')
                            .replace('.', ',')
                            .replace('X', '.'),
                            'Cancelada': 'Sim' if bool(int(row['cancelada'] or 0)) else 'Não',
                            'Emitida em': str(row['emitida_em']),
                        }
                    )
                st.dataframe(dados, width='stretch', hide_index=True)
            else:
                st.info('Nenhuma nota cadastrada ainda.')


if __name__ == '__main__':
    main()
