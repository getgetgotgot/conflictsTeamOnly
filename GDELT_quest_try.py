import requests
import pandas as pd
from io import BytesIO
import zipfile
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

cols = [
    "GlobalEventID", "Day", "MonthYear", "Year", "FractionDate",
    "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode",
    "Actor1EthnicCode", "Actor1Religion1Code", "Actor1Religion2Code",
    "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code",
    "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode",
    "Actor2EthnicCode", "Actor2Religion1Code", "Actor2Religion2Code",
    "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code",
    "IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode",
    "QuadClass", "GoldsteinScale", "NumMentions", "NumSources",
    "NumArticles", "AvgTone",
    "Actor1Geo_Type", "Actor1Geo_FullName", "Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code", "Actor1Geo_ADM2Code", "Actor1Geo_Lat", "Actor1Geo_Long", "Actor1Geo_FeatureID",
    "Actor2Geo_Type", "Actor2Geo_FullName", "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code", "Actor2Geo_ADM2Code", "Actor2Geo_Lat", "Actor2Geo_Long", "Actor2Geo_FeatureID",
    "ActionGeo_Type", "ActionGeo_FullName", "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code", "ActionGeo_ADM2Code", "ActionGeo_Lat", "ActionGeo_Long", "ActionGeo_FeatureID",
    "DATEADDED", "SOURCEURL"
]

def download_file(url):
    try:
        r = requests.get(url, timeout=30)
        z = zipfile.ZipFile(BytesIO(r.content))
        df = pd.read_csv(z.open(z.namelist()[0]), sep="\t", header=None,
                         names=cols, on_bad_lines="skip", low_memory=False)
        for col in df.columns:
            df[col] = df[col].fillna("").astype(str)
        return df
    except Exception as e:
        return None

output_path = "./gdelt_april.parquet" 

# Get file list
print("Fetching master file list...")
master = requests.get("http://data.gdeltproject.org/gdeltv2/masterfilelist.txt").text
rows = [line.split(" ") for line in master.strip().split("\n")]
df_master = pd.DataFrame(rows, columns=["size", "hash", "url"])

def url_to_date(url):
    try:
        return datetime.strptime(url.split("/")[-1][:14], "%Y%m%d%H%M%S")
    except:
        return None

df_master["date"] = df_master["url"].apply(url_to_date)
start = datetime(datetime.now().year, 4, 1)
end = datetime(datetime.now().year, 5, 1)

urls = df_master[
    df_master["url"].str.contains("export") &
    (df_master["date"] >= start) &
    (df_master["date"] < end)
]["url"].tolist()

print(f"Downloading {len(urls)} files...")

# write in chunks of 200 files
chunk_size = 200
first_write = True

for chunk_start in range(0, len(urls), chunk_size):
    chunk_urls = urls[chunk_start:chunk_start + chunk_size]
    chunk_results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_file, url): url for url in chunk_urls}
        for future in as_completed(futures):
            df = future.result()
            if df is not None:
                chunk_results.append(df)

    if chunk_results:
        chunk_df = pd.concat(chunk_results, ignore_index=True)
        chunk_df.to_parquet(
            output_path,
            index=False,
            engine="fastparquet",
            append=not first_write
        )
        first_write = False
        print(f"Written chunk ending at file {chunk_start + chunk_size}/{len(urls)}")
        del chunk_df, chunk_results

print("Done!")
