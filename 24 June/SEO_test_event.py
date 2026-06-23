"""Query global event visibility and add comparable geographic location weights.

This file only does data collection and weighting. It saves the 210-country
DataFrame to CSV. Use SEO_global_visibility_per_event.py to draw the map.
"""

import base64
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests


# ----- Settings -----
RUN_QUERIES = True
EVENT_ROW_INDEX = 1  # Khan Younis, Israel in dataforseo_location_counts.csv.

EVENTS_FILE = Path('dataforseo_location_counts.csv')
LOCATIONS_FILE = Path('dataforseo_google_location_codes.csv')
RESULTS_FILE = Path('khan_younis_global_visibility_results.csv')
BASE_URL = 'https://api.dataforseo.com/v3'
REQUEST_TIMEOUT = (15, 120)
MAX_TASK_ATTEMPTS = 3
RESULT_DEPTH = 10  # Collect the first ten actual News results per country.


def load_env() -> None:
    """Load DataForSEO credentials from .env without storing them in source code."""
    env_file = Path(__file__).with_name('.env')
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_headers() -> dict:
    """Create the HTTP Basic Authentication header required by DataForSEO."""
    load_env()
    login = os.environ.get('DFSEO_LOGIN')
    password = os.environ.get('DFSEO_PASSWORD')
    if not login or not password:
        raise RuntimeError('Set DFSEO_LOGIN and DFSEO_PASSWORD in .env first.')
    token = base64.b64encode(f'{login}:{password}'.encode()).decode()
    return {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}


def prepare_queries() -> pd.DataFrame:
    """Build one identical event query for every unique Country-level location."""
    event = pd.read_csv(EVENTS_FILE).iloc[EVENT_ROW_INDEX]
    if (event['location'], event['country']) != ('Khan Younis', 'Israel'):
        raise ValueError('Check EVENT_ROW_INDEX: it must select Khan Younis, Israel.')

    locations = pd.read_csv(
        LOCATIONS_FILE,
        usecols=['location_code', 'location_name', 'country_iso_code', 'location_type'],
    )
    countries = locations[
        locations['location_type'].eq('Country') & locations['country_iso_code'].notna()
    ].drop_duplicates('country_iso_code').rename(columns={
        'location_code': 'request_location_code',
        'location_name': 'request_country',
    }).copy()

    countries.insert(0, 'event_location', event['location'])
    countries.insert(1, 'event_country', event['country'])
    countries.insert(2, 'keyword_query', event['keyword_query'])
    # se_results_count is retained only as a reference. The substantive
    # comparison uses the actual top-ten titles, URLs, and domains below.
    countries['serp_results_count'] = pd.NA
    countries['top_results_count'] = pd.NA
    countries['top_result_titles'] = '[]'
    countries['top_result_urls'] = '[]'
    countries['top_result_domains'] = '[]'
    countries['url_overlap_with_israel'] = pd.NA
    countries['rbo_with_israel'] = pd.NA
    countries['query_status'] = 'not_run'
    return countries.sort_values('country_iso_code').reset_index(drop=True)


def empty_result(status: str) -> dict:
    """Return the CSV fields used when a query cannot produce result items."""
    return {
        'serp_results_count': pd.NA,
        'top_results_count': pd.NA,
        'top_result_titles': '[]',
        'top_result_urls': '[]',
        'top_result_domains': '[]',
        'query_status': status,
    }


def extract_top_results(task: dict) -> dict:
    """Extract comparable top-ten result content from a successful API task."""
    result = (task.get('result') or [{}])[0]
    # Use DataForSEO's explicit rank when supplied, rather than relying only
    # on the order in which the JSON items happen to be returned.
    items = sorted(
        result.get('items') or [],
        key=lambda item: item.get('rank_absolute', item.get('rank_group', 10**9)),
    )
    urls = [item.get('url') for item in items if item.get('url')]
    titles = [item.get('title') for item in items if item.get('title')]
    domains = [
        item.get('domain') or urlparse(item.get('url', '')).netloc
        for item in items
        if item.get('url') or item.get('domain')
    ]
    return {
        'serp_results_count': result.get('se_results_count'),
        'top_results_count': len(items),
        'top_result_titles': json.dumps(titles, ensure_ascii=False),
        'top_result_urls': json.dumps(urls, ensure_ascii=False),
        'top_result_domains': json.dumps(domains, ensure_ascii=False),
        'query_status': 'ok' if task.get('status_code') == 20000 else 'no_results',
    }


def query_top_results(headers: dict, row: pd.Series) -> dict:
    """Send one live query and return its actual top-ten News result content.

    DataForSEO task error 40201 has proved transient in this workflow, so the
    same task is retried up to three times with a short pause before it is
    finally recorded as an error.
    """
    payload = [{
        'language_code': 'en',
        'keyword': row['keyword_query'],
        'depth': RESULT_DEPTH,
        'search_param': 'tbs=cdr:1,cd_min:01/01/2026,cd_max:05/31/2026',
        'location_code': int(row['request_location_code']),
        'tag': f"global_visibility_{row['country_iso_code']}",
    }]
    for attempt in range(1, MAX_TASK_ATTEMPTS + 1):
        try:
            response = requests.post(
                f'{BASE_URL}/serp/google/news/live/advanced',
                headers=headers, json=payload, timeout=REQUEST_TIMEOUT,
            )
            api_response = response.json()
        except requests.exceptions.Timeout:
            return empty_result('request_timeout')
        except (requests.RequestException, ValueError) as error:
            return empty_result(f'error: {type(error).__name__}')

        if response.status_code != 200:
            return empty_result(
                f"http_error {response.status_code}: "
                f"{api_response.get('status_code')} {api_response.get('status_message')}"
            )

        task = (api_response.get('tasks') or [{}])[0]
        task_code = task.get('status_code')
        if task_code in {20000, 40102}:
            return extract_top_results(task)

        if task_code == 40201 and attempt < MAX_TASK_ATTEMPTS:
            print(f'  Temporary task error 40201; retrying ({attempt}/{MAX_TASK_ATTEMPTS})...')
            time.sleep(5)
            continue
        return empty_result(f"task_error {task_code}: {task.get('status_message')}")


def rank_biased_overlap(reference_urls: list[str], comparison_urls: list[str], p: float = 0.9) -> float:
    """Calculate extrapolated Rank-Biased Overlap for two finite ranked URL lists.

    ``p`` controls top-heaviness: p=0.9 gives higher ranks more influence while
    still using all ten results. The extrapolated finite-list form returns 1.0
    when two lists are identical, including their rank order.
    """
    depth = min(len(reference_urls), len(comparison_urls))
    if depth == 0:
        return pd.NA
    reference_seen, comparison_seen = set(), set()
    weighted_overlap = 0.0
    agreement_at_depth = 0.0
    for rank in range(1, depth + 1):
        reference_seen.add(reference_urls[rank - 1])
        comparison_seen.add(comparison_urls[rank - 1])
        agreement_at_depth = len(reference_seen & comparison_seen) / rank
        weighted_overlap += (1 - p) * (p ** (rank - 1)) * agreement_at_depth
    return weighted_overlap + agreement_at_depth * (p ** depth)


def add_israel_result_similarity(results: pd.DataFrame) -> pd.DataFrame:
    """Add set-based and rank-based similarity to the Israel result page.

    Jaccard overlap = shared URLs / URLs appearing in either result list.
    A value of 1 means the two top-ten URL sets are identical; 0 means they
    share no URLs. RBO additionally rewards the same URLs appearing at the
    same high ranks. Neither metric represents total article volume.
    """
    enriched = results.copy()
    israel_row = enriched[enriched['country_iso_code'].eq('IL')]
    if israel_row.empty:
        return enriched
    israel_urls_list = json.loads(israel_row.iloc[0]['top_result_urls'])
    israel_urls = set(israel_urls_list)

    def jaccard(urls_json):
        urls = set(json.loads(urls_json))
        union = israel_urls | urls
        return len(israel_urls & urls) / len(union) if union else pd.NA

    enriched['url_overlap_with_israel'] = enriched['top_result_urls'].map(jaccard)
    enriched['rbo_with_israel'] = enriched['top_result_urls'].map(
        lambda urls_json: rank_biased_overlap(israel_urls_list, json.loads(urls_json))
    )
    return enriched


def query_event_visibility() -> pd.DataFrame:
    """Start a fresh 210-country run and checkpoint the CSV after every row."""
    # Start from a clean query table as requested. The existing checkpoint is
    # overwritten before the first API call, so all 210 countries are queried again.
    results = prepare_queries()
    if not RUN_QUERIES:
        return results

    results.to_csv(RESULTS_FILE, index=False)
    headers = api_headers()
    for number, index in enumerate(results.index, start=1):
        row = results.loc[index]
        print(f'{number}/{len(results)}: {row["request_country"]}')
        result_data = query_top_results(headers, row)
        results.loc[index, list(result_data)] = list(result_data.values())
        results.to_csv(RESULTS_FILE, index=False)
    return add_israel_result_similarity(results)


if __name__ == '__main__':
    global_visibility_df = query_event_visibility()
    global_visibility_df = add_israel_result_similarity(global_visibility_df)
    global_visibility_df.to_csv(RESULTS_FILE, index=False)
    print(f'Saved {len(global_visibility_df)} rows to {RESULTS_FILE.resolve()}')
