from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from nfse.domain.constants import DEFAULT_PRESTADOR, DEFAULT_TOMADOR
from nfse.domain.models import Prestador, RpsData, Tomador


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
        conn.execute(
            """
            INSERT INTO prestadores (cnpj, inscricao_municipal, razao_social, telefone, email)
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM prestadores WHERE cnpj = ?
            )
            """,
            (
                DEFAULT_PRESTADOR.cnpj,
                DEFAULT_PRESTADOR.inscricao_municipal,
                DEFAULT_PRESTADOR.razao_social,
                DEFAULT_PRESTADOR.telefone,
                DEFAULT_PRESTADOR.email,
                DEFAULT_PRESTADOR.cnpj,
            ),
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


def listar_prestadores(db_path: Path) -> list[Prestador]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT cnpj, inscricao_municipal, razao_social, telefone, email
            FROM prestadores
            ORDER BY id
            """
        ).fetchall()
    return [
        Prestador(
            cnpj=row[0],
            inscricao_municipal=row[1],
            razao_social=row[2],
            telefone=row[3],
            email=row[4],
        )
        for row in rows
    ]


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
