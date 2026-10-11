# Intelligence layer

[`venue_history.py`](venue_history.py) loads and checks the compact [venue snapshot](../data/venue_history.json) built by [`build_venue_history.py`](build_venue_history.py) from dated Cricsheet records. [`venue_registry.py`](venue_registry.py) canonicalizes reviewed venue names; [`pitch_analyzer.py`](pitch_analyzer.py) supplies curated priors when history is insufficient. History is descriptive and deliberately leaves score multipliers neutral until backtests support them.

[`weather_fetcher.py`](weather_fetcher.py) uses Open-Meteo, [`injury_detector.py`](injury_detector.py) handles availability/news signals, [`shap_explainer.py`](shap_explainer.py) computes model drivers, and [`llm_analyst.py`](llm_analyst.py) provides optional Ollama narrative with a heuristic fallback. External weather, news and Ollama may be unavailable without blocking the core model. `OPEN_METEO_BASE`, `OLLAMA_BASE_URL` and `OLLAMA_MODEL` are optional configuration.

Run `python -m unittest tests.test_venue_history tests.test_explanation_faithfulness -v` from the root with the project dependencies. See the [Pitch Control evidence rules](../docs/PITCH_CONTROL_REPORT_PLAN.md) and [root architecture](../README.md).
