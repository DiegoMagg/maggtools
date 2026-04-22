from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from nfse.domain.constants import DEFAULT_TOMADOR
from nfse.domain.models import Prestador, RpsData, Tomador

_SNOWFLAKE_LOCK = threading.Lock()
_SNOWFLAKE_LAST_MS = 0
_SNOWFLAKE_SEQ = 0
_SNOWFLAKE_SEQ_MAX = 99


def _next_snowflake_id() -> int:
    global _SNOWFLAKE_LAST_MS, _SNOWFLAKE_SEQ
    with _SNOWFLAKE_LOCK:
        now_ms = int(time.time() * 1000)
        if now_ms == _SNOWFLAKE_LAST_MS:
            _SNOWFLAKE_SEQ += 1
            if _SNOWFLAKE_SEQ > _SNOWFLAKE_SEQ_MAX:
                while now_ms <= _SNOWFLAKE_LAST_MS:
                    time.sleep(0.001)
                    now_ms = int(time.time() * 1000)
                _SNOWFLAKE_SEQ = 0
        else:
            _SNOWFLAKE_SEQ = 0

        _SNOWFLAKE_LAST_MS = now_ms
        return (now_ms * 100) + _SNOWFLAKE_SEQ


def init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prestadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cnpj TEXT NOT NULL UNIQUE,
                inscricao_municipal TEXT NOT NULL,
                razao_social TEXT NOT NULL,
                telefone TEXT,
                email TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tomadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                razao_social TEXT NOT NULL,
                email TEXT,
                logradouro TEXT NOT NULL,
                numero TEXT NOT NULL,
                bairro TEXT NOT NULL,
                codigo_pais TEXT,
                codigo_end_postal TEXT,
                cidade_exterior TEXT,
                estado_exterior TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nfse_emitidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_dps INTEGER NOT NULL UNIQUE,
                ambiente TEXT NOT NULL,
                id_dps TEXT,
                chave_acesso TEXT,
                codigo_municipio TEXT NOT NULL,
                cnpj_prestador TEXT NOT NULL,
                serie TEXT NOT NULL,
                valor_servicos TEXT NOT NULL,
                resposta_json TEXT NOT NULL,
                emitida_em TEXT NOT NULL,
                cancelada INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        nfse_columns = {str(row[1]) for row in conn.execute('PRAGMA table_info(nfse_emitidas)').fetchall()}
        if 'cancelada' not in nfse_columns:
            conn.execute('ALTER TABLE nfse_emitidas ADD COLUMN cancelada INTEGER NOT NULL DEFAULT 0')
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO tomadores (
                razao_social,
                email,
                logradouro,
                numero,
                bairro,
                codigo_pais,
                codigo_end_postal,
                cidade_exterior,
                estado_exterior
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM tomadores
                WHERE razao_social = ?
                  AND logradouro = ?
                  AND numero = ?
            )
            """,
            (
                DEFAULT_TOMADOR.razao_social,
                DEFAULT_TOMADOR.email,
                DEFAULT_TOMADOR.logradouro,
                DEFAULT_TOMADOR.numero,
                DEFAULT_TOMADOR.bairro,
                DEFAULT_TOMADOR.codigo_pais,
                DEFAULT_TOMADOR.codigo_end_postal,
                DEFAULT_TOMADOR.cidade_exterior,
                DEFAULT_TOMADOR.estado_exterior,
                DEFAULT_TOMADOR.razao_social,
                DEFAULT_TOMADOR.logradouro,
                DEFAULT_TOMADOR.numero,
            ),
        )
        conn.commit()


def carregar_configuracoes(db_path: Path) -> dict[str, str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute('SELECT key, value FROM app_config').fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def salvar_configuracoes(db_path: Path, configuracoes: dict[str, str]) -> None:
    if not configuracoes:
        return
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO app_config (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            [(key, value) for key, value in configuracoes.items()],
        )
        conn.commit()


def obter_prestador(db_path: Path) -> Prestador | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT cnpj, inscricao_municipal, razao_social, telefone, email
            FROM prestadores
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return Prestador(
        cnpj=row[0],
        inscricao_municipal=row[1],
        razao_social=row[2],
        telefone=row[3],
        email=row[4],
    )


def salvar_prestador(db_path: Path, prestador: Prestador) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute('DELETE FROM prestadores')
        conn.execute(
            """
            INSERT INTO prestadores (cnpj, inscricao_municipal, razao_social, telefone, email)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                prestador.cnpj,
                prestador.inscricao_municipal,
                prestador.razao_social,
                prestador.telefone,
                prestador.email,
            ),
        )
        conn.commit()


def listar_tomadores(db_path: Path) -> list[Tomador]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                razao_social,
                email,
                logradouro,
                numero,
                bairro,
                codigo_pais,
                codigo_end_postal,
                cidade_exterior,
                estado_exterior
            FROM tomadores
            ORDER BY id
            """
        ).fetchall()
    return [
        Tomador(
            razao_social=row[0],
            email=row[1],
            logradouro=row[2],
            numero=row[3],
            bairro=row[4],
            codigo_pais=row[5],
            codigo_end_postal=row[6],
            cidade_exterior=row[7],
            estado_exterior=row[8],
        )
        for row in rows
    ]


def cadastrar_tomador(db_path: Path, tomador: Tomador) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO tomadores (
                razao_social,
                email,
                logradouro,
                numero,
                bairro,
                codigo_pais,
                codigo_end_postal,
                cidade_exterior,
                estado_exterior
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM tomadores
                WHERE razao_social = ?
                  AND logradouro = ?
                  AND numero = ?
            )
            """,
            (
                tomador.razao_social,
                tomador.email,
                tomador.logradouro,
                tomador.numero,
                tomador.bairro,
                tomador.codigo_pais,
                tomador.codigo_end_postal,
                tomador.cidade_exterior,
                tomador.estado_exterior,
                tomador.razao_social,
                tomador.logradouro,
                tomador.numero,
            ),
        )
        conn.commit()
    return cursor.rowcount > 0


def proximo_numero_dps(db_path: Path) -> int:
    _ = db_path
    return _next_snowflake_id()


def registrar_nf_emitida(
    db_path: Path,
    numero_dps: int,
    ambiente: str,
    data: RpsData,
    response_payload: dict,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO nfse_emitidas (
                numero_dps,
                ambiente,
                id_dps,
                chave_acesso,
                codigo_municipio,
                cnpj_prestador,
                serie,
                valor_servicos,
                resposta_json,
                emitida_em,
                cancelada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                numero_dps,
                ambiente,
                response_payload.get('idDps') or response_payload.get('idDPS'),
                response_payload.get('chaveAcesso'),
                data.servico.codigo_municipio,
                data.prestador.cnpj,
                data.serie,
                f'{data.servico.valor_servicos:.2f}',
                json.dumps(response_payload, ensure_ascii=True),
                datetime.now().isoformat(timespec='seconds'),
                0,
            ),
        )
        conn.commit()


def registrar_nf_importada(
    db_path: Path,
    *,
    numero_dps: int,
    ambiente: str,
    id_dps: str,
    chave_acesso: str,
    codigo_municipio: str,
    cnpj_prestador: str,
    serie: str,
    valor_servicos: str,
    resposta_payload: dict,
    emitida_em: str = '',
) -> None:
    emitida_em_resolvida = emitida_em.strip() or datetime.now().isoformat(timespec='seconds')
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO nfse_emitidas (
                numero_dps,
                ambiente,
                id_dps,
                chave_acesso,
                codigo_municipio,
                cnpj_prestador,
                serie,
                valor_servicos,
                resposta_json,
                emitida_em,
                cancelada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(numero_dps),
                ambiente,
                id_dps,
                chave_acesso,
                codigo_municipio,
                cnpj_prestador,
                serie,
                valor_servicos,
                json.dumps(resposta_payload, ensure_ascii=True),
                emitida_em_resolvida,
                0,
            ),
        )
        conn.commit()


def atualizar_nfse_classificacao(
    db_path: Path,
    *,
    registro_id: int,
    ambiente: str,
    cancelada: bool,
) -> bool:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE nfse_emitidas
            SET ambiente = ?, cancelada = ?
            WHERE id = ?
            """,
            (ambiente.strip(), 1 if cancelada else 0, int(registro_id)),
        )
        conn.commit()
    return cursor.rowcount > 0


def existe_nfse_por_identificadores(
    db_path: Path,
    *,
    id_dps: str,
    chave_acesso: str,
) -> bool:
    id_dps_limpo = id_dps.strip()
    chave_limpa = chave_acesso.strip()
    if not id_dps_limpo and not chave_limpa:
        return False

    filtros = []
    parametros: list[object] = []
    if id_dps_limpo:
        filtros.append('id_dps = ?')
        parametros.append(id_dps_limpo)
    if chave_limpa:
        filtros.append('chave_acesso = ?')
        parametros.append(chave_limpa)

    where_clause = ' OR '.join(filtros)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            f"""
            SELECT 1
            FROM nfse_emitidas
            WHERE {where_clause}
            LIMIT 1
            """,
            parametros,
        ).fetchone()
    return row is not None


def listar_nfse_emitidas(
    db_path: Path,
    limit: int = 200,
    offset: int = 0,
    termo: str = '',
    emitida_inicio: str = '',
    emitida_fim: str = '',
    ambiente: str = '',
    cancelada: str = '',
) -> list[dict[str, str | int]]:
    filtros = []
    parametros: list[object] = []
    termo_limpo = termo.strip()
    if termo_limpo:
        filtros.append(
            """
            (
                CAST(numero_dps AS TEXT) LIKE ?
                OR COALESCE(ambiente, '') LIKE ?
                OR COALESCE(chave_acesso, '') LIKE ?
                OR COALESCE(cnpj_prestador, '') LIKE ?
                OR COALESCE(id_dps, '') LIKE ?
            )
            """
        )
        termo_like = f'%{termo_limpo}%'
        parametros.extend([termo_like, termo_like, termo_like, termo_like, termo_like])

    inicio_limpo = emitida_inicio.strip()
    if inicio_limpo:
        filtros.append('emitida_em >= ?')
        parametros.append(inicio_limpo)

    fim_limpo = emitida_fim.strip()
    if fim_limpo:
        filtros.append('emitida_em <= ?')
        parametros.append(fim_limpo)

    ambiente_limpo = ambiente.strip()
    if ambiente_limpo:
        filtros.append('ambiente = ?')
        parametros.append(ambiente_limpo)

    cancelada_limpo = cancelada.strip()
    if cancelada_limpo in {'0', '1'}:
        filtros.append('cancelada = ?')
        parametros.append(cancelada_limpo)

    where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ''
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                id,
                numero_dps,
                ambiente,
                id_dps,
                chave_acesso,
                codigo_municipio,
                cnpj_prestador,
                serie,
                valor_servicos,
                emitida_em,
                cancelada
            FROM nfse_emitidas
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
            OFFSET ?
            """,
            [*parametros, int(limit), int(offset)],
        ).fetchall()
    return [
        {
            'id': int(row[0]),
            'numero_dps': int(row[1]),
            'ambiente': str(row[2] or ''),
            'id_dps': str(row[3] or ''),
            'chave_acesso': str(row[4] or ''),
            'codigo_municipio': str(row[5] or ''),
            'cnpj_prestador': str(row[6] or ''),
            'serie': str(row[7] or ''),
            'valor_servicos': str(row[8] or ''),
            'emitida_em': str(row[9] or ''),
            'cancelada': bool(int(row[10] or 0)),
        }
        for row in rows
    ]


def contar_nfse_emitidas(
    db_path: Path,
    termo: str = '',
    emitida_inicio: str = '',
    emitida_fim: str = '',
    ambiente: str = '',
    cancelada: str = '',
) -> int:
    filtros = []
    parametros: list[object] = []
    termo_limpo = termo.strip()
    if termo_limpo:
        filtros.append(
            """
            (
                CAST(numero_dps AS TEXT) LIKE ?
                OR COALESCE(ambiente, '') LIKE ?
                OR COALESCE(chave_acesso, '') LIKE ?
                OR COALESCE(cnpj_prestador, '') LIKE ?
                OR COALESCE(id_dps, '') LIKE ?
            )
            """
        )
        termo_like = f'%{termo_limpo}%'
        parametros.extend([termo_like, termo_like, termo_like, termo_like, termo_like])

    inicio_limpo = emitida_inicio.strip()
    if inicio_limpo:
        filtros.append('emitida_em >= ?')
        parametros.append(inicio_limpo)

    fim_limpo = emitida_fim.strip()
    if fim_limpo:
        filtros.append('emitida_em <= ?')
        parametros.append(fim_limpo)

    ambiente_limpo = ambiente.strip()
    if ambiente_limpo:
        filtros.append('ambiente = ?')
        parametros.append(ambiente_limpo)

    cancelada_limpo = cancelada.strip()
    if cancelada_limpo in {'0', '1'}:
        filtros.append('cancelada = ?')
        parametros.append(cancelada_limpo)

    where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ''
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(1)
            FROM nfse_emitidas
            {where_clause}
            """,
            parametros,
        ).fetchone()
    return int(row[0] if row else 0)


def obter_resposta_nfse_por_id(db_path: Path, registro_id: int) -> dict:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT resposta_json
            FROM nfse_emitidas
            WHERE id = ?
            """,
            (int(registro_id),),
        ).fetchone()
    if row is None:
        return {}
    try:
        return json.loads(str(row[0]))
    except json.JSONDecodeError:
        return {}
