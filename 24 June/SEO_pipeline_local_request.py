import pandas as pd
import re
import os
import json
import base64
import requests


def load_dotenv(path):
    """Load simple KEY=VALUE settings from a local .env file."""
    try:
        with open(path, encoding='utf-8') as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# DataForSEO credentials
DFSEO_LOGIN = os.environ.get('DFSEO_LOGIN')
DFSEO_PASSWORD = os.environ.get('DFSEO_PASSWORD')

if not DFSEO_LOGIN or not DFSEO_PASSWORD:
    raise RuntimeError(
        'Set the DFSEO_LOGIN and DFSEO_PASSWORD environment variables before running this script.'
    )

BASE_URL = 'https://api.dataforseo.com/v3'
# (connection timeout, response read timeout).  News searches can legitimately
# take more than one minute, especially when no results are found.
REQUEST_TIMEOUT = (15, 120)
HEADERS = {
    'Authorization': 'Basic ' + base64.b64encode(f'{DFSEO_LOGIN}:{DFSEO_PASSWORD}'.encode()).decode(),
    'Content-Type': 'application/json',
}

conflict_set = pd.read_csv('GEDEvent_v26_0_4.csv')

COUNTRY_ALIASES = {
    # Canonical DataForSEO Country-level names.  The two Congos must not be
    # collapsed into one alias because they use different location codes.
    'Congo, Democratic Republic of the': 'Democratic Republic of the Congo',
    'Congo, DR': 'Democratic Republic of the Congo',
    'DR Congo': 'Democratic Republic of the Congo',
    'Democratic Republic of Congo': 'Democratic Republic of the Congo',
    'Republic of Congo': 'Republic of the Congo',
    'Congo, Republic of the': 'Republic of the Congo',
    'United Arab Emirates (UAE)': 'United Arab Emirates',
    'UAE': 'United Arab Emirates',
}

COUNTRY_TO_ISO3 = {
    'Afghanistan': 'AFG',
    'Algeria': 'DZA',
    'Bangladesh': 'BGD',
    'Belize': 'BLZ',
    'Brazil': 'BRA',
    'Burkina Faso': 'BFA',
    'Burundi': 'BDI',
    'Cameroon': 'CMR',
    'Central African Republic': 'CAF',
    'Chad': 'TCD',
    'Colombia': 'COL',
    'Democratic Republic of the Congo': 'COD',
    'Republic of the Congo': 'COG',
    'Ecuador': 'ECU',
    'Ethiopia': 'ETH',
    'Ghana': 'GHA',
    'Guatemala': 'GTM',
    'Haiti': 'HTI',
    'India': 'IND',
    'Indonesia': 'IDN',
    'Iran': 'IRN',
    'Iraq': 'IRQ',
    'Israel': 'ISR',
    'Jamaica': 'JAM',
    'Kenya': 'KEN',
    'Lebanon': 'LBN',
    'Mali': 'MLI',
    'Mexico': 'MEX',
    'Mozambique': 'MOZ',
    'Myanmar': 'MMR',
    'Niger': 'NER',
    'Nigeria': 'NGA',
    'Pakistan': 'PAK',
    'Papua New Guinea': 'PNG',
    'Philippines': 'PHL',
    'Russia': 'RUS',
    'Saudi Arabia': 'SAU',
    'Somalia': 'SOM',
    'South Africa': 'ZAF',
    'South Sudan': 'SSD',
    'Sudan': 'SDN',
    'Syria': 'SYR',
    'Thailand': 'THA',
    'Turkey': 'TUR',
    'Uganda': 'UGA',
    'Ukraine': 'UKR',
    'United Arab Emirates': 'ARE',
    'Venezuela': 'VEN',
    'Yemen': 'YEM',
}

SUCCESSFUL_TASK_STATUSES = {20000, 40102}  # 40102 means a valid search with zero results

LOCATION_SUFFIXES = re.compile(r'\b(town|city|village|district|province|county|region|municipality|governorate|canton|prefecture|state|department|refugee camp|state border crossing)\b', flags=re.IGNORECASE)


def clean_location(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    text = LOCATION_SUFFIXES.sub('', text).strip()
    text = re.sub(r'[\s,;]+$', '', text).strip()
    return text or None


def clean_country(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    text = re.sub(r'\s*\(.*?\)\s*', '', text).strip()
    return text or None


def clean_country_code(value):
    if pd.isna(value) or value is None:
        return None
    normalized = COUNTRY_ALIASES.get(str(value).strip(), str(value).strip())
    return COUNTRY_TO_ISO3.get(normalized)


def build_location_map():
    """Fetch the full locations list from DataForSEO and return a name->code map.
    This is resilient to minor schema differences: it looks for common name/code keys.
    """
    try:
        resp = requests.get(f'{BASE_URL}/serp/google/locations', headers=HEADERS, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        tasks = data.get('tasks') or []
        if not tasks:
            return {}
        result = tasks[0].get('result') or []

        mapping = {}

        def walk(items):
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                names = []
                if 'name' in it:
                    names.append(it.get('name'))
                if 'location_name' in it:
                    names.append(it.get('location_name'))
                if 'display_name' in it:
                    names.append(it.get('display_name'))
                # try common code keys
                code = it.get('location_code') or it.get('code') or it.get('id') or it.get('location_id')
                for n in names:
                    if n:
                        mapping[str(n).strip().lower()] = code
                # recurse into children lists if present
                for k, v in it.items():
                    if isinstance(v, list):
                        walk(v)

        walk(result)
        return mapping
    except Exception:
        return {}


def find_location_code(location_map, country_name, location_name):
    """Try to find a suitable location_code for the given country/location.
    Priority: country_name -> country_name + location_name -> location_name alone.
    """
    if not location_map:
        return None
    if country_name:
        code = location_map.get(str(country_name).strip().lower())
        if code:
            return code
    if country_name and location_name:
        combo = f"{location_name}, {country_name}".strip().lower()
        code = location_map.get(combo)
        if code:
            return code
    if location_name:
        code = location_map.get(str(location_name).strip().lower())
        if code:
            return code
    return None


conflict_set['location_clean'] = conflict_set['where_coordinates'].apply(clean_location)
conflict_set['country_clean'] = conflict_set['country'].apply(clean_country)
conflict_set['country_code'] = conflict_set['country_clean'].apply(clean_country_code)

unique_pairs = conflict_set[['location_clean', 'country_clean', 'country_code']].drop_duplicates()
unique_pairs = unique_pairs[unique_pairs['location_clean'].notna() & unique_pairs['country_clean'].notna()].head(20)

SEARCH_TERMS = 'conflict OR war OR attack OR armed OR terror OR bomb OR violence OR strike OR protest'

coverage = []
location_map = build_location_map()
failed_requests = []

for idx, row in unique_pairs.iterrows():
    location = row['location_clean']
    country = row['country_clean']
    country_code = row['country_code']
    location_name = COUNTRY_ALIASES.get(country, country)

    keyword = f'({SEARCH_TERMS}) AND "{location_name}" AND "{location}"'

    # try to find a location_code (preferred); do not send the invalid `location_name` field
    location_code = find_location_code(location_map, country, location)

    if not location_code:
        failed_requests.append({
            'country': country,
            'location': location,
            'error': 'unsupported_location',
            'response_text': (
                'No valid DataForSEO Google location_code was found for this country. '
                'The request was skipped.'
            ),
        })
        print(f'Skipping {country} | {location}: no valid DataForSEO location_code.')
        continue

    task = {
        'language_code': 'en',
        'keyword': keyword,
        'depth': 1,
        'search_param': 'tbs=cdr:1,cd_min:01/01/2026,cd_max:05/31/2026',
        'tag': f'{idx}_{location_name}_{location}',
    }
    if location_code:
        task['location_code'] = location_code

    post_data = [task]

    print(f'Posting request for {location_name} | {location} (using location_code={location_code})')
    print('payload=', json.dumps(post_data, ensure_ascii=False))

    try:
        response = requests.post(
            f'{BASE_URL}/serp/google/news/live/advanced',
            headers=HEADERS,
            json=post_data,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout as exc:
        # Do not automatically retry a live endpoint: the server may have
        # completed the request after the client stopped waiting, and a retry
        # could therefore create a duplicate billed request.
        failed_requests.append({
            'country': country,
            'location': location,
            'error': 'request_timeout',
            'response_text': str(exc),
        })
        print(f'Request timed out for {country} | {location}; recorded and continuing.')
        continue
    except requests.RequestException as exc:
        failed_requests.append({
            'country': country,
            'location': location,
            'error': 'request_error',
            'response_text': str(exc),
        })
        print(f'Request failed for {country} | {location}; recorded and continuing.')
        continue

    if response.status_code != 200:
        failed_requests.append({
            'country': country,
            'location': location,
            'status_code': response.status_code,
            'response_text': response.text[:1000],
        })
        print('HTTP error', response.status_code)
        continue

    try:
        data = response.json()
    except ValueError:
        failed_requests.append({
            'country': country,
            'location': location,
            'error': 'invalid_json',
            'response_text': response.text[:1000],
        })
        print('Invalid JSON for', country, location)
        continue

    if data.get('status_code') != 20000:
        failed_requests.append({
            'country': country,
            'location': location,
            'status_code': data.get('status_code'),
            'status_message': data.get('status_message'),
            'response': data,
        })
        print('API error', data.get('status_code'), data.get('status_message'))
        continue

    # A successful envelope can still contain an invalid individual task.  This
    # was the source of the misleading "no_se_results_count" entries in the
    # previous failure CSV (for example: 40501 Invalid Field: location_name).
    response_tasks = data.get('tasks') or []
    task_errors = [
        response_task for response_task in response_tasks
        if response_task.get('status_code') not in SUCCESSFUL_TASK_STATUSES
    ]
    if task_errors:
        first_error = task_errors[0]
        failed_requests.append({
            'country': country,
            'location': location,
            'error': 'task_error',
            'task_status_code': first_error.get('status_code'),
            'task_status_message': first_error.get('status_message'),
            'response': json.dumps(data, ensure_ascii=False),
        })
        print(
            'Task error',
            first_error.get('status_code'),
            first_error.get('status_message'),
            'for', country, location,
        )
        continue

    article_count = None
    for task in response_tasks:
        for result in task.get('result', []) or []:
            if result.get('se_results_count') is not None:
                article_count = result['se_results_count']
                break
        if article_count is not None:
            break

    if article_count is None:
        failed_requests.append({
            'country': country,
            'location': location,
            'error': 'no_se_results_count',
            'response': data,
        })
        print('No se_results_count found for', country, location)
        continue

    coverage.append({
        'location': location,
        'country': country,
        'country_code': country_code,
        'keyword_query': keyword,
        'article_count': article_count,
    })
    print(f'{country} | {location} -> {article_count}')

coverage_df = pd.DataFrame(coverage)
coverage_df.to_csv('dataforseo_location_counts.csv', index=False)

failed_columns = [
    'country', 'location', 'error', 'status_code', 'status_message',
    'task_status_code', 'task_status_message', 'response_text', 'response',
]
pd.DataFrame(failed_requests, columns=failed_columns).to_csv(
    'dataforseo_failed_tasks.csv', index=False
)

print(f'Done. Saved {len(coverage_df)} rows. {len(failed_requests)} failures recorded.')
