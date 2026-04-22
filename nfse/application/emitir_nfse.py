from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal


def parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            'Formato invalido para --data-emissao. Use ISO 8601 (ex.: 2026-04-22T13:46:01-03:00).'
        ) from exc


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except Exception as exc:
        raise argparse.ArgumentTypeError('Valor decimal invalido.') from exc
