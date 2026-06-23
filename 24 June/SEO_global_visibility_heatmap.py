"""Map rank-based Google News result divergence from an existing CSV.

This script never calls DataForSEO. It visualises RBO-based differences between
each country's top-ten result page and the Israel-configured reference page.
"""

from pathlib import Path

import folium
import pandas as pd
from branca.colormap import linear
from countryinfo import all_countries
from folium.plugins import HeatMap


RESULTS_FILE = Path('khan_younis_global_visibility_results.csv')
MAP_FILE = Path('khan_younis_ranked_result_divergence_map.html')
EVENT_COORDINATES = (31.346, 34.306)
COORDINATE_FALLBACKS = {
    'AQ': (-82.8628, 135.0000), 'BQ': (12.1784, -68.2385),
    'CW': (12.1696, -68.9900), 'SX': (18.0425, -63.0548),
    'UM': (19.2823, 166.6470),
}


def country_coordinates() -> dict[str, tuple[float, float]]:
    """Return offline display coordinates by ISO-2 code; they are not a metric."""
    coordinates = {}
    for country in all_countries():
        info = country.info()
        iso_code = info.get('ISO', {}).get('alpha2')
        latlng = info.get('latlng') or []
        if iso_code and len(latlng) == 2:
            coordinates[iso_code] = tuple(latlng)
    coordinates.update(COORDINATE_FALLBACKS)
    return coordinates


def prepare_plot_data(results: pd.DataFrame) -> pd.DataFrame:
    """Convert rank similarity into a 0-1 divergence score for the map.

    RBO=1 means identical ranked URL lists. Therefore divergence = 1-RBO;
    higher values represent a more different Google News result page.
    """
    required = {'request_country', 'country_iso_code', 'query_status', 'rbo_with_israel'}
    missing = required.difference(results.columns)
    if missing:
        raise ValueError(f'Results CSV is missing required columns: {sorted(missing)}')

    plot = results.copy()
    plot['rbo_with_israel'] = pd.to_numeric(plot['rbo_with_israel'], errors='coerce')
    plot['coordinates'] = plot['country_iso_code'].map(country_coordinates())
    plot['latitude'] = plot['coordinates'].map(lambda point: point[0] if isinstance(point, tuple) else pd.NA)
    plot['longitude'] = plot['coordinates'].map(lambda point: point[1] if isinstance(point, tuple) else pd.NA)
    plot = plot.dropna(subset=['rbo_with_israel', 'latitude', 'longitude']).copy()
    plot['ranked_result_divergence'] = 1 - plot['rbo_with_israel']
    return plot


def create_heatmap(results: pd.DataFrame, output_file: Path = MAP_FILE) -> Path:
    """Create an interactive world map of rank-based result divergence."""
    plot = prepare_plot_data(results)
    if plot.empty:
        raise ValueError('No completed query results are available to plot.')

    maximum = plot['ranked_result_divergence'].max()
    plot['heat_intensity'] = plot['ranked_result_divergence'] / maximum if maximum else 0

    world_map = folium.Map(location=EVENT_COORDINATES, zoom_start=2, tiles='CartoDB positron')
    folium.Marker(
        EVENT_COORDINATES,
        popup='Event: Khan Younis, Israel<br>Reference: Israel-configured English Google News',
        icon=folium.Icon(color='red'),
    ).add_to(world_map)
    HeatMap(plot[['latitude', 'longitude', 'heat_intensity']].values.tolist(), radius=25, blur=20).add_to(world_map)

    colour_scale = linear.YlOrRd_09.scale(0, maximum or 1)
    colour_scale.caption = 'Ranked top-ten URL divergence from Israel (1 − RBO)'
    colour_scale.add_to(world_map)
    for _, row in plot.iterrows():
        popup = (
            f"<b>{row['request_country']}</b> ({row['country_iso_code']})<br>"
            f"Rank-Biased Overlap with Israel: {row['rbo_with_israel']:.3f}<br>"
            f"Ranked result divergence: {row['ranked_result_divergence']:.3f}<br>"
            f"Query status: {row['query_status']}"
        )
        folium.CircleMarker(
            [row['latitude'], row['longitude']],
            radius=4 + 7 * row['ranked_result_divergence'],
            color='#333', weight=1, fill=True,
            fill_color=colour_scale(row['ranked_result_divergence']),
            fill_opacity=0.7, popup=popup,
        ).add_to(world_map)

    world_map.save(output_file)
    return output_file.resolve()


if __name__ == '__main__':
    heatmap_file = create_heatmap(pd.read_csv(RESULTS_FILE))
    print(f'Map saved to: {heatmap_file}')
