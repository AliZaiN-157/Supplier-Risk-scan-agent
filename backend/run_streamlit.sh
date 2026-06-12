#!/bin/bash
# Run the Streamlit API test UI
# Usage: bash backend/run_streamlit.sh

cd "$(dirname "$0")"
uv run --group dev streamlit run streamlit_app.py
