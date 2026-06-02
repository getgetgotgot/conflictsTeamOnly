import pandas as pd
from google.cloud import bigquery
import re

client = bigquery.Client(project="INSERT YOUR PROJECT NAME MOTHERFUCKERRR !!!!")

conflict_set = pd.read_csv("C://Users//Ana//Downloads//GEDEvent_v26_0_4.csv")

conflict_themes = [
    'ARMEDCONFLICT', 'ASSASSINATION', 'BATTLE', 'CEASEFIRE', 'CLASH', 'COMBATANT', 
    'CONFLICT', 'CRACKDOWN', 'GUNFIRE', 'HOSTILITIES', 'INSURGENCY', 'MASSACRE', 
    'MILITARY_ACTION', 'PROTEST_ARMED', 'RIOT', 'TERRORISM', 'VIOLENCE', 'WAR'
]

theme_pattern = '|'.join(conflict_themes)

def clean_location(loc):
    if pd.isna(loc):
        return None
    loc = str(loc).strip()
    suffixes = r'\b(town|city|village|district|province|county|region|municipality|governorate|canton|prefecture|state|department|refugee camp|state border crossing)\b'
    loc = re.sub(suffixes, '', loc, flags=re.IGNORECASE).strip()
    loc = re.sub(r'[\s,;]+$', '', loc).strip()
    return loc if loc else None

conflict_set['location_clean'] = conflict_set['where_coordinates'].apply(clean_location)

# Get unique locations only
unique_locations = conflict_set['location_clean'].dropna().unique()

print(f"Processing {len(unique_locations)} locations...")

coverage = []

for location in unique_locations:
    location_escaped = location.replace("'", "\\'")
    
    query_count = f"""
    SELECT COUNT(*) as article_count
    FROM `gdelt-bq.gdeltv2.gkg_partitioned`
    WHERE _PARTITIONTIME >= TIMESTAMP('2026-04-01') AND _PARTITIONTIME <= TIMESTAMP('2026-05-01')
    AND REGEXP_CONTAINS(V2Locations, r'{location_escaped}')
    AND REGEXP_CONTAINS(V2Themes, r'{theme_pattern}')
    """
    
    try:
        result_count = client.query(query_count).result()
        article_count = list(result_count)[0]['article_count']
    except Exception as e:
        print(f"Error counting {location}: {e}")
        continue
    
    if article_count == 0:
        continue
    
    print(f"{location}: {article_count} articles")
    
    coverage.append({
        'location': location,
        'conflict_articles': article_count,
        'top_5_actors': None
    })

coverage_df = pd.DataFrame(coverage)
coverage_df.to_csv('INSERT COMPUTA FILE PATH MOTHERFUCKAAAA//location_coverage_1.csv', index=False)