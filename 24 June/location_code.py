"""Download DataForSEO's Google location list into a CSV lookup table."""

import base64
import json
import os
from pathlib import Path

import pandas as pd
import requests


BASE_URL = 'https://api.dataforseo.com/v3'
OUTPUT_FILE = Path('dataforseo_google_location_codes.csv')
REQUEST_TIMEOUT = (15, 120)


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    if not path.exists():
        return

    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_locations() -> list[dict]:
    load_dotenv(Path(__file__).with_name('.env'))
    login = os.environ.get('DFSEO_LOGIN')
    password = os.environ.get('DFSEO_PASSWORD')
    if not login or not password:
        raise RuntimeError('Set DFSEO_LOGIN and DFSEO_PASSWORD in .env or environment variables.')

    credentials = base64.b64encode(f'{login}:{password}'.encode()).decode()
    response = requests.get(
        f'{BASE_URL}/app_data/google/locations',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json',
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get('status_code') != 20000:
        raise RuntimeError(
            f"DataForSEO error {payload.get('status_code')}: {payload.get('status_message')}"
        )

    rows = []
    for task in payload.get('tasks') or []:
        if task.get('status_code') != 20000:
            raise RuntimeError(
                f"Task error {task.get('status_code')}: {task.get('status_message')}"
            )
        rows.extend(item for item in (task.get('result') or []) if isinstance(item, dict))
    return rows


def main() -> None:
    locations = get_locations()
    if not locations:
        raise RuntimeError('The locations endpoint returned no rows.')

    preferred_columns = [
        'location_code',
        'location_name',
        'country_iso_code',
        'location_type',
        'location_code_parent',
    ]
    table = pd.DataFrame(locations)
    table = table.reindex(columns=preferred_columns + [
        column for column in table.columns if column not in preferred_columns
    ])
    table = table.sort_values(
        by=['country_iso_code', 'location_name'], kind='stable', na_position='last'
    )
    table.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

    print(f'Saved {len(table):,} locations to {OUTPUT_FILE.resolve()}')
    iran = table[table['country_iso_code'].eq('IR')]
    print(f'Iran rows: {len(iran):,}')
    if not iran.empty:
        print(iran[preferred_columns].to_string(index=False))


if __name__ == '__main__':
    main()
