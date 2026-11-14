from app.schemas import LatLonPoint
from app.services.srtm_elevation import (
    calculate_polygon_centroid_and_area_ha,
    calculate_slope_from_elevations,
)


def test_calculate_slope_flat_terrain():
    terrain = calculate_slope_from_elevations(
        elevations=[250.0, 250.0, 250.0, 250.0, 250.0],
        dx_m=180.0,
        dy_m=180.0,
    )
    assert terrain.elevation_m == 250.0
    assert terrain.slope_pct == 0.0
    assert terrain.terrain_class == "Plano / Suave"
    assert terrain.erosion_risk == "Bajo"


def test_calculate_slope_sloped_hillside():
    terrain = calculate_slope_from_elevations(
        elevations=[260.0, 270.0, 250.0, 260.0, 260.0],
        dx_m=180.0,
        dy_m=180.0,
    )
    assert abs(terrain.slope_pct - 11.11) < 0.05
    assert terrain.terrain_class == "Inclinado / Ladera"
    assert terrain.erosion_risk == "Alto"


def test_polygon_area_and_slope_metrics():
    # ~1km x 1km square near equator => ~100 ha
    square = [
        LatLonPoint(lat=0.0, lon=0.0),
        LatLonPoint(lat=0.008983, lon=0.0),
        LatLonPoint(lat=0.008983, lon=0.008983),
        LatLonPoint(lat=0.0, lon=0.008983),
    ]
    c_lat, c_lon, area_ha = calculate_polygon_centroid_and_area_ha(square)
    assert 95.0 <= area_ha <= 105.0
    assert 0.004 <= c_lat <= 0.005

    terrain = calculate_slope_from_elevations(
        elevations=[200.0, 200.0, 200.0, 200.0, 200.0],
        dx_m=180.0,
        dy_m=180.0,
        polygon_points=[(p.lat, p.lon) for p in square],
        polygon_elevations=[200.0, 230.0, 210.0, 195.0],
        area_ha=area_ha,
    )
    assert terrain.area_ha == area_ha
    assert terrain.polygon_vertices == 4
    assert terrain.min_elevation_m == 195.0
    assert terrain.max_elevation_m == 230.0
    assert terrain.max_slope_pct >= 2.5
