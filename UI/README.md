# Internal Streamlit interfaces

[`product_ui.py`](product_ui.py) and [`model_ui.py`](model_ui.py) are local/legacy evaluation and product views; [`components/cricket_field.py`](components/cricket_field.py) supplies a visual component. The public website is the Next.js app in [`frontend/`](../frontend/README.md). Streamlit is not required to start the FastAPI backend or static site.

Install `requirements.txt` and run a module with `python -m streamlit run UI/model_ui.py` from the root if you need the internal dashboard and its saved data/model artifacts. The core `unittest` suite tests model contracts separately; no visual Streamlit verification is claimed. See [root setup](../README.md).
