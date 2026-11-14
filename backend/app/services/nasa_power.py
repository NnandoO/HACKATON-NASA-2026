import calendar
from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Tuple

import httpx
import pandas as pd

from app.config import settings
from app.schemas import (
    AnnualClimatePoint,
    ClimateAnalysis,
    ClimateAnomalies,
    MonthlyClimatePoint,
    MonthlyClimatologyPoint,
)
from app.services.geo_cache import geo_cache

logger = logging.getLogger(__name__)

NASA_FILL_VALUE = -999.0

MONTH_NAMES_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def fetch_nasa_power_raw(
    lat: float,
    lon: float,
    start_year: int = 2015,
    end_year: int = 2025,
) -> Dict[str, Any]:
    """Perform HTTP GET request to NASA POWER monthly agroclimatology API (climate + SMAP wetness + solar)."""
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,GWETTOP,GWETROOT,ALLSKY_SFC_SW_DWN",
        "community": "AG",
        "longitude": round(lon, 4),
        "latitude": round(lat, 4),
        "start": start_year,
        "end": end_year,
        "format": "JSON",
    }
    with httpx.Client(timeout=settings.http_timeout_seconds) as client:
        response = client.get(settings.nasa_power_base_url, params=params)
        response.raise_for_status()
        return response.json()


def _build_fallback_raw(lat: float, start_year: int, end_year: int) -> Dict[str, Any]:
    """Deterministic fallback dataset used only if NASA POWER API is unreachable."""
    abs_lat = abs(lat)
    base_temp = max(10.0, 27.5 - abs_lat * 0.34)
    amp = 1.8 if abs_lat < 23.5 else 6.5
    base_rain_day = 3.2 if abs_lat < 23.5 else 2.2
    phase = 0 if lat >= 0 else math.pi

    t2m, t2m_max, t2m_min, prec, rh2m, gwettop, gwetroot, solar = (
        {},
        {},
        {},
        {},
        {},
        {},
        {},
        {},
    )

    for year in range(start_year, end_year + 1):
        recent_shift = 1.0 if year >= end_year - 2 else 0.0
        rain_factor = 0.85 if year >= end_year - 2 else 1.0
        for month in range(1, 13):
            key = f"{year}{month:02d}"
            seasonal = math.cos(((month - 7) / 12.0) * 2 * math.pi + phase)
            temp = round(base_temp + amp * seasonal + recent_shift, 2)
            t2m[key] = temp
            t2m_max[key] = round(temp + 5.5, 2)
            t2m_min[key] = round(temp - 5.8, 2)
            prec[key] = round(max(0.3, (base_rain_day + 1.4 * seasonal) * rain_factor), 2)
            rh2m[key] = round(76.0 if abs_lat < 23.5 else 66.0, 1)
            gwettop[key] = round(max(0.25, min(0.85, 0.55 + 0.14 * seasonal)), 2)
            gwetroot[key] = round(max(0.30, min(0.85, 0.58 + 0.10 * seasonal)), 2)
            solar[key] = round(17.5 + 3.5 * seasonal, 2)

    return {
        "properties": {
            "parameter": {
                "T2M": t2m,
                "T2M_MAX": t2m_max,
                "T2M_MIN": t2m_min,
                "PRECTOTCORR": prec,
                "RH2M": rh2m,
                "GWETTOP": gwettop,
                "GWETROOT": gwetroot,
                "ALLSKY_SFC_SW_DWN": solar,
            }
        }
    }


def _find_tropical_dry_and_wet_quarters(monthly_rain_means: Dict[int, float]) -> Tuple[List[int], List[int]]:
    best_dry_sum = float("inf")
    best_wet_sum = -1.0
    dry_months = [1, 2, 3]
    wet_months = [9, 10, 11]

    for start_m in range(1, 13):
        window = [((start_m - 1 + offset) % 12) + 1 for offset in range(3)]
        rain_sum = sum(monthly_rain_means.get(m, 0.0) for m in window)
        if rain_sum < best_dry_sum:
            best_dry_sum = rain_sum
            dry_months = window
        if rain_sum > best_wet_sum:
            best_wet_sum = rain_sum
            wet_months = window

    return dry_months, wet_months


def _hargreaves_monthly_et0_mm(
    tmean: float, tmax: float, tmin: float, solar_mj: float, days: int
) -> float:
    """Estimate monthly reference evapotranspiration ET0 (mm) using radiation-adjusted Hargreaves."""
    # Convert solar MJ/m2/day to equivalent water evaporation mm/day (Rs / 2.45)
    et0_day = 0.0135 * (tmean + 17.78) * max(1.0, solar_mj / 2.45) * (0.45 + 0.04 * max(2.0, tmax - tmin))
    return max(15.0, et0_day * days)


def parse_nasa_power_with_pandas(
    raw_json: Dict[str, Any],
    lat: float,
    source: str = "nasa_power_api",
) -> ClimateAnalysis:
    """Process NASA POWER JSON with pandas including SMAP-assimilated wetness, solar radiation and ET0."""
    params = raw_json.get("properties", {}).get("parameter", {})
    t2m_map: Dict[str, float] = params.get("T2M", {})
    t2m_max_map: Dict[str, float] = params.get("T2M_MAX", {})
    t2m_min_map: Dict[str, float] = params.get("T2M_MIN", {})
    prec_map: Dict[str, float] = params.get("PRECTOTCORR", {})
    rh2m_map: Dict[str, float] = params.get("RH2M", {})
    gwettop_map: Dict[str, float] = params.get("GWETTOP", {})
    gwetroot_map: Dict[str, float] = params.get("GWETROOT", {})
    solar_map: Dict[str, float] = params.get("ALLSKY_SFC_SW_DWN", {})

    rows: List[Dict[str, Any]] = []
    for ym_key, t2m_val in t2m_map.items():
        if len(ym_key) != 6 or not ym_key.isdigit():
            continue
        year = int(ym_key[:4])
        month = int(ym_key[4:6])
        if month < 1 or month > 12:
            continue

        prec_day = prec_map.get(ym_key, NASA_FILL_VALUE)
        tmax_val = t2m_max_map.get(ym_key, NASA_FILL_VALUE)
        tmin_val = t2m_min_map.get(ym_key, NASA_FILL_VALUE)
        rh_val = rh2m_map.get(ym_key, NASA_FILL_VALUE)
        wet_top = gwettop_map.get(ym_key, NASA_FILL_VALUE)
        wet_root = gwetroot_map.get(ym_key, NASA_FILL_VALUE)
        solar_val = solar_map.get(ym_key, NASA_FILL_VALUE)

        if t2m_val <= NASA_FILL_VALUE or prec_day <= NASA_FILL_VALUE:
            continue

        days_in_month = calendar.monthrange(year, month)[1]
        rain_mm = float(prec_day) * days_in_month
        tmean = float(t2m_val)
        tmax = float(tmax_val) if tmax_val > NASA_FILL_VALUE else tmean + 5.0
        tmin = float(tmin_val) if tmin_val > NASA_FILL_VALUE else tmean - 5.0
        solar = float(solar_val) if solar_val > NASA_FILL_VALUE else 17.5
        et0_mm = _hargreaves_monthly_et0_mm(tmean, tmax, tmin, solar, days_in_month)

        rows.append(
            {
                "period": f"{year}-{month:02d}",
                "year": year,
                "month": month,
                "temp_c": tmean,
                "temp_max_c": tmax,
                "temp_min_c": tmin,
                "rh2m_pct": float(rh_val) if rh_val > NASA_FILL_VALUE else 68.0,
                "soil_wetness_top": float(wet_top) if wet_top > NASA_FILL_VALUE else 0.55,
                "soil_wetness_root": float(wet_root) if wet_root > NASA_FILL_VALUE else 0.58,
                "solar_mj_m2_day": solar,
                "et0_mm": et0_mm,
                "rain_mm": rain_mm,
            }
        )

    if not rows:
        raise ValueError("No valid monthly NASA POWER records found in response.")

    df = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)

    month_counts = df.groupby("year")["month"].count()
    complete_years = month_counts[month_counts >= 10].index.tolist()
    df = df[df["year"].isin(complete_years)].copy()

    is_tropical = abs(lat) < 23.5
    hemisphere = "Norte" if lat >= 0 else "Sur"

    clim_df = (
        df.groupby("month", as_index=False)
        .agg(
            avg_temp_c=("temp_c", "mean"),
            avg_temp_min_c=("temp_min_c", "mean"),
            avg_rain_mm=("rain_mm", "mean"),
            avg_rh2m_pct=("rh2m_pct", "mean"),
            avg_soil_wetness_top=("soil_wetness_top", "mean"),
            avg_et0_mm=("et0_mm", "mean"),
        )
        .sort_values("month")
    )
    monthly_rain_means = {int(r["month"]): float(r["avg_rain_mm"]) for _, r in clim_df.iterrows()}

    if is_tropical:
        dry_months, _ = _find_tropical_dry_and_wet_quarters(monthly_rain_means)
        focus_months = dry_months
        dry_names = "-".join(MONTH_NAMES_ES[m] for m in dry_months)
        climate_zone = "Tropical"
        seasonal_focus_label = f"Trimestre seco ({dry_names})"
    else:
        focus_months = [6, 7, 8] if lat >= 0 else [12, 1, 2]
        climate_zone = f"Templada ({hemisphere})"
        seasonal_focus_label = "Verano"

    df["is_focus_season"] = df["month"].isin(focus_months)

    annual_all = df.groupby("year", as_index=False).agg(
        avg_temp_c=("temp_c", "mean"),
        total_rain_mm=("rain_mm", "sum"),
        avg_soil_wetness_top=("soil_wetness_top", "mean"),
        total_et0_mm=("et0_mm", "sum"),
    )
    annual_focus = (
        df[df["is_focus_season"]]
        .groupby("year", as_index=False)
        .agg(
            summer_avg_temp_c=("temp_c", "mean"),
            summer_rain_mm=("rain_mm", "sum"),
        )
    )
    annual_df = pd.merge(annual_all, annual_focus, on="year", how="left").sort_values("year")

    years = annual_df["year"].tolist()
    recent_window = min(3, max(1, len(years) // 3))
    recent_years = years[-recent_window:]
    baseline_years = years[:-recent_window] if len(years) > recent_window else years

    baseline_df = annual_df[annual_df["year"].isin(baseline_years)]
    recent_df = annual_df[annual_df["year"].isin(recent_years)]
    recent_monthly_slice = df[df["year"].isin(recent_years)]

    base_temp = float(baseline_df["avg_temp_c"].mean())
    rec_temp = float(recent_df["avg_temp_c"].mean())
    temp_anomaly = rec_temp - base_temp

    base_focus_temp = float(baseline_df["summer_avg_temp_c"].mean())
    rec_focus_temp = float(recent_df["summer_avg_temp_c"].mean())
    focus_temp_anomaly = rec_focus_temp - base_focus_temp

    base_rain = float(baseline_df["total_rain_mm"].mean())
    rec_rain = float(recent_df["total_rain_mm"].mean())
    rain_anomaly_pct = ((rec_rain - base_rain) / base_rain * 100.0) if base_rain > 0 else 0.0

    base_focus_rain = float(baseline_df["summer_rain_mm"].mean())
    rec_focus_rain = float(recent_df["summer_rain_mm"].mean())
    focus_rain_anomaly_pct = (
        ((rec_focus_rain - base_focus_rain) / base_focus_rain * 100.0)
        if base_focus_rain > 0
        else 0.0
    )

    frost_months_rows = clim_df[clim_df["avg_temp_min_c"] <= 3.0]
    frost_risk_months = [MONTH_NAMES_ES[int(m)] for m in frost_months_rows["month"].tolist()]
    min_temp_coldest = float(clim_df["avg_temp_min_c"].min())
    frost_risk_present = len(frost_risk_months) > 0 or min_temp_coldest <= 3.0

    avg_rh2m = float(recent_monthly_slice["rh2m_pct"].mean())
    high_humidity_risk = avg_rh2m >= 80.0

    avg_wet_top = float(recent_monthly_slice["soil_wetness_top"].mean())
    avg_wet_root = float(recent_monthly_slice["soil_wetness_root"].mean())
    dry_soil_rows = clim_df[clim_df["avg_soil_wetness_top"] < 0.45]
    dry_soil_months = [MONTH_NAMES_ES[int(m)] for m in dry_soil_rows["month"].tolist()]

    annual_et0 = float(recent_df["total_et0_mm"].mean())
    water_balance = rec_rain - annual_et0

    drier_recent = rain_anomaly_pct <= -8.0 or focus_rain_anomaly_pct <= -10.0 or avg_wet_top < 0.45
    hotter_recent = temp_anomaly >= 0.5 or focus_temp_anomaly >= 0.6

    alerts: List[str] = []
    if focus_temp_anomaly >= 0.5:
        alerts.append(
            f"{seasonal_focus_label} reciente {focus_temp_anomaly:+.1f} °C más caluroso que la media histórica ({baseline_years[0]}-{baseline_years[-1]})."
        )
    elif temp_anomaly >= 0.4:
        alerts.append(
            f"Tendencia térmica anual al alza ({temp_anomaly:+.1f} °C en los últimos años)."
        )

    if focus_rain_anomaly_pct <= -10.0:
        alerts.append(
            f"{seasonal_focus_label} más seco recientemente: caída de {abs(focus_rain_anomaly_pct):.0f}% en precipitación."
        )
    if dry_soil_months:
        alerts.append(
            f"Humedad superficial del suelo baja (<45%) en {', '.join(dry_soil_months)} (SMAP/POWER): priorizar cultivos eficientes en agua."
        )
    if water_balance < -200.0:
        alerts.append(
            f"Balance hídrico deficitario ({water_balance:.0f} mm/año: lluvia {rec_rain:.0f} mm vs ET₀ {annual_et0:.0f} mm); ideal cultivos de secano o cobertura."
        )
    elif rain_anomaly_pct >= 12.0:
        alerts.append(
            f"Incremento reciente de lluvias anuales (+{rain_anomaly_pct:.0f}%), vigilar drenaje y escorrentía."
        )

    if frost_risk_present:
        months_str = ", ".join(frost_risk_months) if frost_risk_months else "meses fríos"
        alerts.append(
            f"Riesgo de heladas detectado (T° mínima media hasta {min_temp_coldest:.1f} °C en {months_str})."
        )
    if high_humidity_risk:
        alerts.append(
            f"Humedad relativa promedio alta ({avg_rh2m:.0f}%): mayor presión potencial de hongos foliares."
        )

    if not alerts:
        alerts.append(
            "Clima y humedad del suelo estables respecto a la media histórica de la NASA para esta parcela."
        )

    anomalies = ClimateAnomalies(
        climate_zone=climate_zone,
        seasonal_focus_label=seasonal_focus_label,
        baseline_period=f"{baseline_years[0]}-{baseline_years[-1]}",
        recent_period=f"{recent_years[0]}-{recent_years[-1]}",
        baseline_avg_temp_c=round(base_temp, 2),
        recent_avg_temp_c=round(rec_temp, 2),
        temp_anomaly_c=round(temp_anomaly, 2),
        summer_temp_anomaly_c=round(focus_temp_anomaly, 2),
        baseline_annual_rain_mm=round(base_rain, 1),
        recent_annual_rain_mm=round(rec_rain, 1),
        rain_anomaly_pct=round(rain_anomaly_pct, 1),
        summer_rain_anomaly_pct=round(focus_rain_anomaly_pct, 1),
        min_temp_coldest_month_c=round(min_temp_coldest, 1),
        avg_rh2m_pct=round(avg_rh2m, 1),
        avg_soil_wetness_top=round(avg_wet_top, 2),
        avg_soil_wetness_root=round(avg_wet_root, 2),
        dry_soil_months=dry_soil_months,
        annual_et0_mm=round(annual_et0, 1),
        water_balance_mm=round(water_balance, 1),
        frost_risk_months=frost_risk_months,
        drier_recent_trend=drier_recent,
        hotter_recent_trend=hotter_recent,
        frost_risk_present=frost_risk_present,
        high_humidity_risk=high_humidity_risk,
        climate_alerts=alerts,
    )

    annual_series = [
        AnnualClimatePoint(
            year=int(row["year"]),
            avg_temp_c=round(float(row["avg_temp_c"]), 2),
            summer_avg_temp_c=round(float(row["summer_avg_temp_c"]), 2),
            total_rain_mm=round(float(row["total_rain_mm"]), 1),
            summer_rain_mm=round(float(row["summer_rain_mm"]), 1),
            avg_soil_wetness_top=round(float(row["avg_soil_wetness_top"]), 2),
            total_et0_mm=round(float(row["total_et0_mm"]), 1),
        )
        for _, row in annual_df.iterrows()
    ]

    recent_monthly_df = df.tail(24)
    recent_monthly_series = [
        MonthlyClimatePoint(
            period=str(row["period"]),
            year=int(row["year"]),
            month=int(row["month"]),
            temp_c=round(float(row["temp_c"]), 2),
            temp_max_c=round(float(row["temp_max_c"]), 2),
            temp_min_c=round(float(row["temp_min_c"]), 2),
            rh2m_pct=round(float(row["rh2m_pct"]), 1),
            soil_wetness_top=round(float(row["soil_wetness_top"]), 2),
            soil_wetness_root=round(float(row["soil_wetness_root"]), 2),
            solar_mj_m2_day=round(float(row["solar_mj_m2_day"]), 2),
            et0_mm=round(float(row["et0_mm"]), 1),
            rain_mm=round(float(row["rain_mm"]), 1),
        )
        for _, row in recent_monthly_df.iterrows()
    ]

    monthly_climatology = [
        MonthlyClimatologyPoint(
            month=int(row["month"]),
            month_name=MONTH_NAMES_ES[int(row["month"])],
            avg_temp_c=round(float(row["avg_temp_c"]), 2),
            avg_temp_min_c=round(float(row["avg_temp_min_c"]), 2),
            avg_rain_mm=round(float(row["avg_rain_mm"]), 1),
            avg_rh2m_pct=round(float(row["avg_rh2m_pct"]), 1),
            avg_soil_wetness_top=round(float(row["avg_soil_wetness_top"]), 2),
            avg_et0_mm=round(float(row["avg_et0_mm"]), 1),
        )
        for _, row in clim_df.iterrows()
    ]

    return ClimateAnalysis(
        source=source,
        hemisphere=hemisphere,
        anomalies=anomalies,
        annual_series=annual_series,
        recent_monthly_series=recent_monthly_series,
        monthly_climatology=monthly_climatology,
    )


def fetch_nasa_power_daily_raw(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """Fetch recent daily precipitation from NASA POWER daily API to detect extreme storm days."""
    params = {
        "parameters": "PRECTOTCORR",
        "community": "AG",
        "longitude": round(lon, 4),
        "latitude": round(lat, 4),
        "start": start_date,
        "end": end_date,
        "format": "JSON",
    }
    with httpx.Client(timeout=min(8.0, settings.http_timeout_seconds)) as client:
        response = client.get(settings.nasa_power_daily_url, params=params)
        response.raise_for_status()
        return response.json()


def get_daily_storm_metrics(lat: float, lon: float, end_year: int) -> Dict[str, Any]:
    """Count daily storm events (>=25mm and >=40mm/day) over the last 2 years using SQLite cache."""
    start_date = f"{end_year - 1}0101"
    end_date = f"{end_year}1231"
    cache_key = geo_cache.grid_key(lat, lon, step_deg=0.05, extra=f"daily:{start_date}-{end_date}")
    cached = geo_cache.get_json("nasa_power_daily", cache_key)
    if cached is not None:
        return cached

    try:
        raw = fetch_nasa_power_daily_raw(lat=lat, lon=lon, start_date=start_date, end_date=end_date)
        prec_map = raw.get("properties", {}).get("parameter", {}).get("PRECTOTCORR", {})
        valid_vals = [float(v) for v in prec_map.values() if v is not None and float(v) > -900.0]
        if not valid_vals:
            raise ValueError("No valid daily precipitation readings")
        metrics = {
            "extreme_rain_days_gt40mm": sum(1 for v in valid_vals if v >= 40.0),
            "heavy_rain_days_gt25mm": sum(1 for v in valid_vals if v >= 25.0),
            "max_daily_rain_mm": round(max(valid_vals), 1),
            "daily_source": "nasa_power_daily_api",
        }
        geo_cache.set_json(
            "nasa_power_daily",
            cache_key,
            metrics,
            ttl_seconds=settings.cache_climate_ttl_hours * 3600,
        )
        return metrics
    except Exception as exc:
        logger.debug("NASA POWER daily API skipped/failed (%s)", exc)
        return {
            "extreme_rain_days_gt40mm": 0,
            "heavy_rain_days_gt25mm": 0,
            "max_daily_rain_mm": 0.0,
            "daily_source": "unavailable",
        }


def _apply_daily_storm_metrics(analysis: ClimateAnalysis, metrics: Dict[str, Any]) -> ClimateAnalysis:
    ext = int(metrics.get("extreme_rain_days_gt40mm", 0))
    heavy = int(metrics.get("heavy_rain_days_gt25mm", 0))
    max_day = float(metrics.get("max_daily_rain_mm", 0.0))

    analysis.anomalies.extreme_rain_days_gt40mm = ext
    analysis.anomalies.heavy_rain_days_gt25mm = heavy
    analysis.anomalies.max_daily_rain_mm = max_day

    if ext >= 3 or max_day >= 45.0:
        storm_alert = (
            f"Lluvias intensas diarias detectadas (NASA POWER Daily): pico de {max_day:.1f} mm/día "
            f"y {ext} día(s) con >40 mm en los últimos 2 años; reforzar cobertura para evitar erosión."
        )
        if storm_alert not in analysis.anomalies.climate_alerts:
            analysis.anomalies.climate_alerts.append(storm_alert)
    return analysis


def get_climate_analysis(lat: float, lon: float) -> ClimateAnalysis:
    """Fetch NASA POWER historical series (with SQLite cache) and compute climate/water anomalies."""
    end_year = min(2025, datetime.now(timezone.utc).year - 1)
    start_year = end_year - 10
    cache_key = geo_cache.grid_key(lat, lon, step_deg=0.05, extra=f"{start_year}-{end_year}")
    cached = geo_cache.get_json("nasa_power", cache_key)
    if cached is not None:
        analysis = ClimateAnalysis.model_validate(cached)
        if not analysis.source.endswith("_cache"):
            analysis.source = f"{analysis.source}_cache"
        if analysis.anomalies.max_daily_rain_mm == 0.0 and analysis.anomalies.extreme_rain_days_gt40mm == 0:
            daily_metrics = get_daily_storm_metrics(lat=lat, lon=lon, end_year=end_year)
            analysis = _apply_daily_storm_metrics(analysis, daily_metrics)
        return analysis

    try:
        raw_json = fetch_nasa_power_raw(lat=lat, lon=lon, start_year=start_year, end_year=end_year)
        analysis = parse_nasa_power_with_pandas(raw_json, lat=lat, source="nasa_power_api")
        daily_metrics = get_daily_storm_metrics(lat=lat, lon=lon, end_year=end_year)
        analysis = _apply_daily_storm_metrics(analysis, daily_metrics)
        geo_cache.set_json(
            "nasa_power",
            cache_key,
            analysis.model_dump(),
            ttl_seconds=settings.cache_climate_ttl_hours * 3600,
        )
        return analysis
    except Exception as exc:
        logger.warning("NASA POWER API unavailable (%s); using offline fallback estimate.", exc)
        fallback = _build_fallback_raw(lat=lat, start_year=start_year, end_year=end_year)
        return parse_nasa_power_with_pandas(fallback, lat=lat, source="fallback_offline_estimate")
