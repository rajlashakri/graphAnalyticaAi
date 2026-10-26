# GraphAnalytica AI

GraphAnalytica AI is an interactive data-exploration and analytics application. Users upload a CSV or Excel spreadsheet, inspect its contents and quality, explore its schema as a knowledge graph, and ask questions about the data in plain language.

## What the project does

- Loads and validates uploaded CSV and Excel datasets.
- Summarizes dataset size, column names, missing values, and duplicate rows.
- Displays a preview and user-friendly column information.
- Builds a schema knowledge graph connecting a dataset to its columns.
- Answers supported questions about numeric data, such as totals or averages, including grouped results like sales by region.
- Presents analysis results as metrics, tables, or charts.
- Exports the uploaded dataset as a CSV file.

The current prototype uses predefined analytics operations. It does not execute code generated from a user's question, and it does not load sample data automatically; a user must upload a file.

## Technology stack

| Area | Technology |
| --- | --- |
| Programming language | Python |
| Web application | Streamlit |
| Data processing | Pandas, NumPy |
| Charts | Altair and Streamlit charts |
| Schema graph | NetworkX with Graphviz rendering |
| Excel support | OpenPyXL |

## Project structure

```text
.
├── app.py                  # Streamlit interface and dashboard
├── requirements.txt        # Python dependencies
├── sales.csv               # Sample sales dataset
├── data/                   # Data files
└── src/
    ├── __init__.py         # Python package marker
    ├── data_loader.py      # Dataset loading, validation, and summaries
    ├── graph_builder.py    # Schema knowledge graph construction
    ├── analytics_agent.py  # Maps supported questions to analytics
    └── sandbox.py          # Reserved for guarded analytics operations
```

## Run locally

1. Create and activate a Python virtual environment.
2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the application:

   ```bash
   streamlit run app.py
   ```

4. Upload a `.csv` or `.xlsx` file in the app to explore it.

## Current scope and future plans

This is an early prototype focused on dataset upload, profiling, schema visualization, and basic question-driven analytics. Potential future enhancements include richer semantic graph relationships, persistent graph storage with Neo4j, expanded testing and report generation, and optional LLM or LangGraph orchestration. These are future ideas, not features currently required to run the app.

## Data and secrets

Do not commit private datasets, credentials, API keys, or local `.env` files. Keep secrets in local environment configuration and use only non-sensitive sample data in the repository.
