# RaveForge App

A Streamlit workbench for building, validating, and submitting Medidata Rave ODM payloads via [RaveForge](https://github.com/mnouira02/raveforge).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# For local development against the library source:
pip install -e ../raveforge
pip install streamlit

# Or against the published PyPI package:
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Features

- **Connection** — connect to any RWS environment (innovate, uat, prod)
- **Transaction Builder** — fluent UI for Subject → Event → Form → ItemGroup → Item
- **Validation** — pre-build structural checks with severity-aware issue reporting
- **Submit** — post ODM payload to RWS with live diagnostic feedback on failure
- **Study Browser** — browse accessible studies and their sites

## Dependencies

- [`raveforge`](https://github.com/mnouira02/raveforge) — the ODM builder and RWS client library
- [`streamlit`](https://streamlit.io) — the UI framework
