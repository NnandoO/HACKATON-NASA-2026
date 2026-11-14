from app.services.nasa_power import parse_nasa_power_with_pandas


def test_parse_nasa_power_detects_hotter_drier_recent_anomaly():
    t2m = {}
    t2m_max = {}
    t2m_min = {}
    prec = {}
    rh2m = {}

    for year in range(2015, 2026):
        is_recent = year >= 2023
        temp_delta = 1.6 if is_recent else 0.0
        rain_factor = 0.7 if is_recent else 1.0
        for month in range(1, 13):
            key = f"{year}{month:02d}"
            t2m[key] = 20.0 + temp_delta
            t2m_max[key] = 26.0 + temp_delta
            t2m_min[key] = 12.0 + temp_delta
            prec[key] = 2.5 * rain_factor
            rh2m[key] = 65.0
        # Month 13 annual summary entry returned by NASA POWER must be ignored
        t2m[f"{year}13"] = 99.0
        prec[f"{year}13"] = 99.0

    raw = {
        "properties": {
            "parameter": {
                "T2M": t2m,
                "T2M_MAX": t2m_max,
                "T2M_MIN": t2m_min,
                "PRECTOTCORR": prec,
                "RH2M": rh2m,
            }
        }
    }
    analysis = parse_nasa_power_with_pandas(raw, lat=-31.4, source="unit_test")

    assert analysis.hemisphere == "Sur"
    assert analysis.anomalies.climate_zone == "Templada (Sur)"
    assert len(analysis.annual_series) == 11
    assert len(analysis.monthly_climatology) == 12
    assert analysis.anomalies.temp_anomaly_c >= 1.5
    assert analysis.anomalies.rain_anomaly_pct <= -25.0
    assert analysis.anomalies.drier_recent_trend is True
    assert analysis.anomalies.hotter_recent_trend is True
    assert len(analysis.recent_monthly_series) == 24


def test_parse_nasa_power_tropical_zone_uses_dry_quarter():
    t2m, t2m_min, prec, rh2m = {}, {}, {}, {}
    for year in range(2015, 2026):
        is_recent = year >= 2023
        for month in range(1, 13):
            key = f"{year}{month:02d}"
            t2m[key] = 16.0
            # Simulate frost risk in July/August in high-altitude Andes
            t2m_min[key] = 1.5 if month in (7, 8) else 8.0
            # Dry quarter Dec-Jan-Feb gets even drier recently
            base_p = 0.5 if month in (12, 1, 2) else 4.0
            prec[key] = base_p * (0.6 if is_recent and month in (12, 1, 2) else 1.0)
            rh2m[key] = 82.0

    raw = {
        "properties": {
            "parameter": {
                "T2M": t2m,
                "T2M_MIN": t2m_min,
                "PRECTOTCORR": prec,
                "RH2M": rh2m,
            }
        }
    }
    analysis = parse_nasa_power_with_pandas(raw, lat=5.53, source="unit_test")
    assert analysis.anomalies.climate_zone == "Tropical"
    assert "Trimestre seco" in analysis.anomalies.seasonal_focus_label
    assert analysis.anomalies.frost_risk_present is True
    assert analysis.anomalies.high_humidity_risk is True
