from app.services.soilgrids import classify_usda_texture, parse_soilgrids_response


def test_parse_soilgrids_response_and_texture():
    payload = {
        "properties": {
            "layers": [
                {
                    "name": "phh2o",
                    "unit_measure": {"d_factor": 10},
                    "depths": [{"label": "0-5cm", "values": {"mean": 67}}],
                },
                {
                    "name": "clay",
                    "unit_measure": {"d_factor": 10},
                    "depths": [{"label": "0-5cm", "values": {"mean": 336}}],
                },
                {
                    "name": "sand",
                    "unit_measure": {"d_factor": 10},
                    "depths": [{"label": "0-5cm", "values": {"mean": 180}}],
                },
                {
                    "name": "soc",
                    "unit_measure": {"d_factor": 10},
                    "depths": [{"label": "0-5cm", "values": {"mean": 219}}],
                },
            ]
        }
    }
    soil = parse_soilgrids_response(payload)
    assert soil.ph_h2o == 6.7
    assert soil.clay_pct == 33.6
    assert soil.sand_pct == 18.0
    assert abs(soil.silt_pct - 48.4) < 0.2
    assert soil.texture_class == "Franco arcillo-limoso"
    assert classify_usda_texture(10.0, 75.0, 15.0) == "Arenoso"
