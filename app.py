
import json
from io import BytesIO
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.analytics_agent import analyze_question
from src.data_loader import get_dataset_summary, load_dataset
from src.graph_builder import build_schema_graph, get_graph_summary


# -----------------------------------------------------------------------------
# 1. Streamlit page configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="GraphMind AI",
    page_icon=":material/hub:",
    layout="wide",
)


# -----------------------------------------------------------------------------
# 2. UI formatting helpers
# These helpers format graph and analytics output. Data processing is kept in
# the reusable modules under src/.
# -----------------------------------------------------------------------------
def make_graphviz_source(graph):
    """Create a Graphviz schema view using safe generated node identifiers."""
    node_ids = {node: f"n{index}" for index, node in enumerate(graph.nodes)}
    lines = [
        "digraph schema {",
        'graph [rankdir="LR", bgcolor="transparent", pad="0.2"];',
        'node [shape="box", style="rounded,filled", fontname="Arial", color="#d9e4f2", fontcolor="#183153"];',
        'edge [color="#9bb8dc", arrowsize="0.7"];',
    ]
    for node, attributes in graph.nodes(data=True):
        label = str(node)
        color = "#dbeafe" if attributes.get("node_type") == "dataset" else "#f1f6ff"
        if attributes.get("node_type") == "column":
            label += f"\\n{attributes.get('data_type', '')}"
        lines.append(
            f'{node_ids[node]} [label={json.dumps(label)}, fillcolor={json.dumps(color)}];'
        )
    for source, target in graph.edges:
        lines.append(f"{node_ids[source]} -> {node_ids[target]};")
    lines.append("}")
    return "\n".join(lines)


def describe_column_type(series):
    """Map pandas dtypes to labels that make sense to dashboard users."""
    name = str(series.name).strip().lower()
    if name == "id" or name.endswith("_id") or name.endswith(" id") or name in {
        "key", "code"
    }:
        return "Identifier"
    if pd.api.types.is_bool_dtype(series):
        return "Yes / no"
    if pd.api.types.is_datetime64_any_dtype(series) or any(
        token in name for token in ("date", "time", "timestamp")
    ):
        return "Date / time"
    if pd.api.types.is_numeric_dtype(series):
        return "Numeric measure"
    if pd.api.types.is_categorical_dtype(series):
        return "Category"
    return "Text / category"


def show_answer(result):
    """Display analysis output as a scalar, table, or grouped chart."""
    if result["status"] != "success":
        st.warning(result.get("message", "I could not answer that question."))
        return

    value = result["result"]
    operation = result.get("operation", "analysis").replace("_", " ").title()
    metric = result.get("metric", "dataset")
    st.caption(f"{operation} · {metric}")

    if result.get("group_by") and isinstance(value, dict):
        group_column = result["group_by"]
        output = pd.DataFrame(list(value.items()), columns=[group_column, metric])
        st.dataframe(output, hide_index=True, alt=f"{operation} results by {group_column}")
        st.bar_chart(
            output.set_index(group_column),
            alt=f"{metric} {operation.lower()} by {group_column}",
        )
    elif isinstance(value, dict):
        st.dataframe(pd.DataFrame(value), alt=f"{operation} summary results")
    elif isinstance(value, list):
        st.dataframe(pd.DataFrame(value), hide_index=True)
    else:
        st.metric(f"{operation} of {metric}", value)


def remember_uploaded_file():
    """Persist the uploaded bytes so the upload popover can close on rerun."""
    uploaded = st.session_state.get("dataset_upload")
    if uploaded is not None:
        st.session_state.active_dataset_bytes = uploaded.getvalue()
        st.session_state.active_dataset_name = uploaded.name


def reset_uploaded_dataset():
    """Clear the active upload and related conversation state."""
    st.session_state.active_dataset_bytes = None
    st.session_state.active_dataset_name = None
    st.session_state.chat_history = []
    st.session_state.pop("dataset_upload", None)


# -----------------------------------------------------------------------------
# 3. Sidebar navigation
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## :material/hub: GraphMind AI")
    st.caption("From data to insights")
    page = st.radio(
        "Navigation",
        ["Home", "Dataset", "Knowledge graph", "Analytics agent", "Chat history"],
        label_visibility="collapsed",
        format_func=lambda item: {
            "Home": ":material/home:  Home",
            "Dataset": ":material/table_view:  Dataset",
            "Knowledge graph": ":material/hub:  Knowledge graph",
            "Analytics agent": ":material/auto_awesome:  Analytics agent",
            "Chat history": ":material/forum:  Chat history",
        }[item],
    )
    st.space("stretch")
    st.caption("GraphMind AI · Prototype")


# Keep the selected file in session state across Streamlit reruns. Once the
# callback stores it, the upload popover is removed from the page, which closes
# it automatically; the same header space then offers a reset action.
st.session_state.setdefault("active_dataset_bytes", None)
st.session_state.setdefault("active_dataset_name", None)
st.session_state.setdefault("chat_history", [])

# -----------------------------------------------------------------------------
# 4. Upload and validate the user's dataset
# No sample data is loaded automatically; stop here until a file is uploaded.
# -----------------------------------------------------------------------------
title_col, upload_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title("GraphMind AI" if page == "Home" else page, icon=":material/hub:")
with upload_col:
    if st.session_state.active_dataset_bytes is None:
        with st.popover("Upload new data", icon=":material/upload_file:"):
            st.file_uploader(
                "Choose a CSV or Excel file",
                type=["csv", "xlsx"],
                help="Upload a CSV or Excel workbook",
                key="dataset_upload",
                on_change=remember_uploaded_file,
            )
    else:
        st.button(
            "Reset data",
            icon=":material/refresh:",
            on_click=reset_uploaded_dataset,
            help="Remove the current dataset and upload another file",
        )

if st.session_state.active_dataset_bytes is None:
    st.info("Upload a CSV or Excel file to start exploring your dataset.")
    st.stop()

try:
    uploaded_buffer = BytesIO(st.session_state.active_dataset_bytes)
    dataset_name = st.session_state.active_dataset_name
    uploaded_buffer.name = dataset_name
    df = load_dataset(uploaded_buffer)
except ValueError as error:
    st.error(str(error), title="Could not load this dataset")
    st.stop()

# -----------------------------------------------------------------------------
# 5. Shared dataset metadata
# Calculate the summary and graph once so every page can reuse them.
# -----------------------------------------------------------------------------
summary = get_dataset_summary(df)
graph = build_schema_graph(df, dataset_name=dataset_name)
graph_summary = get_graph_summary(graph)

# Dataset name/status and export action, displayed above the selected page.
with st.container(horizontal=True, vertical_alignment="center"):
    st.markdown(f"**{dataset_name}**")
    st.badge("Loaded", icon=":material/check_circle:", color="green")
    st.caption(
        f"Rows: {summary['rows']:,}  ·  Columns: {summary['columns']}"
    )
    st.download_button(
        "Export CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=Path(dataset_name).stem + ".csv",
        mime="text/csv",
        icon=":material/download:",
    )

# -----------------------------------------------------------------------------
# 6. Home dashboard
# KPI cards, data preview/profile, schema graph, key insights, and Q&A assistant.
# -----------------------------------------------------------------------------
if page == "Home":
    dashboard_col, assistant_col = st.columns([2.35, 1], gap="medium")

    # Main dashboard: dataset metrics and analysis panels.
    with dashboard_col:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Total rows", f"{summary['rows']:,}", border=True)
        metric_cols[1].metric("Total columns", summary["columns"], border=True)
        metric_cols[2].metric(
            "Missing values", f"{sum(summary['missing_values'].values()):,}", border=True
        )
        metric_cols[3].metric("Duplicate rows", summary["duplicate_rows"], border=True)

        # Recent rows and a breakdown of the dataset's column types.
        preview_col, profile_col = st.columns([1.6, 1], gap="small")
        with preview_col:
            with st.container(border=True, height="stretch"):
                st.subheader("Dataset preview")
                st.dataframe(
                    df.head(5),
                    hide_index=True,
                    alt="Preview of the first five dataset rows",
                )
                st.caption(f"Showing {min(5, len(df)):,} of {len(df):,} rows")

        with profile_col:
            with st.container(border=True, height="stretch"):
                st.subheader("Column information")
                # Show a useful breakdown for a categorical field instead of
                # a chart of low-level pandas data types. Prefer Product;
                # otherwise choose the first categorical column.
                categorical_columns = [
                    column
                    for column in df.columns
                    if describe_column_type(df[column]) in {"Text / category", "Category"}
                ]
                product_column = next(
                    (
                        column
                        for column in categorical_columns
                        if "product" in str(column).lower()
                    ),
                    None,
                )
                category_column = product_column or (
                    categorical_columns[0] if categorical_columns else None
                )
                numeric_columns = [
                    column
                    for column in df.select_dtypes(include="number").columns
                    if describe_column_type(df[column]) != "Identifier"
                ]
                sales_column = next(
                    (
                        column
                        for column in numeric_columns
                        if str(column).strip().lower() == "sales"
                    ),
                    numeric_columns[0] if numeric_columns else None,
                )

                if category_column is not None:
                    category_counts = (
                        df[category_column]
                        .fillna("Missing")
                        .astype(str)
                        .value_counts()
                        .rename_axis(category_column)
                        .rename("Orders")
                        .reset_index()
                    )
                    if sales_column is not None:
                        sales_by_category = (
                            df.assign(
                                **{
                                    category_column: df[category_column]
                                    .fillna("Missing")
                                    .astype(str)
                                }
                            )
                            .groupby(category_column, dropna=False)[sales_column]
                            .sum()
                            .rename("Total sales")
                            .reset_index()
                        )
                        category_profile = category_counts.merge(
                            sales_by_category,
                            on=category_column,
                            how="outer",
                        )
                        chart_measure = "Total sales"
                        chart_title = f"Sales by {category_column}"
                    else:
                        category_profile = category_counts
                        chart_measure = "Orders"
                        chart_title = f"Orders by {category_column}"

                    category_chart = (
                        alt.Chart(category_profile)
                        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                        .encode(
                            y=alt.Y(f"{category_column}:N", sort="-x", title=None),
                            x=alt.X(f"{chart_measure}:Q", title=chart_measure),
                            color=alt.value("#3478f6"),
                            tooltip=[category_column, "Orders", chart_measure]
                            if sales_column is not None
                            else [category_column, "Orders"],
                        )
                        .properties(height=210, title=chart_title)
                    )
                    st.altair_chart(
                        category_chart,
                        alt=f"{chart_measure} grouped by {category_column}",
                    )
                    st.dataframe(
                        category_profile,
                        hide_index=True,
                        height=150,
                        alt=f"Order and sales totals by {category_column}",
                    )
                else:
                    st.info(
                        "No product or category column found. Add a text column "
                        "such as Product or Region to see a category breakdown."
                    )

        # Schema visualization and automatically calculated summary insights.
        graph_col, insights_col = st.columns([1.2, 1], gap="small")
        with graph_col:
            with st.container(border=True, height="stretch"):
                st.subheader("Knowledge graph")
                st.graphviz_chart(
                    make_graphviz_source(graph),
                    alt="Schema graph connecting the dataset and its columns",
                )
                st.caption(
                    f"{graph_summary['node_count']} nodes · "
                    f"{graph_summary['edge_count']} relationships"
                )

        with insights_col:
            with st.container(border=True, height="stretch"):
                st.subheader("Key insights")
                # Treat identifier fields as keys, not measures: Order_ID
                # should count orders rather than sum the ID values.
                identifier_columns = [
                    column
                    for column in df.columns
                    if describe_column_type(df[column]) == "Identifier"
                ]
                measure_columns = [
                    column
                    for column in df.select_dtypes(include="number").columns
                    if column not in identifier_columns
                ]
                category_columns = [
                    column
                    for column in df.columns
                    if describe_column_type(df[column]) in {"Text / category", "Category"}
                ]

                order_column = next(
                    (
                        column
                        for column in identifier_columns
                        if "order" in str(column).lower()
                    ),
                    identifier_columns[0] if identifier_columns else None,
                )
                if order_column is not None:
                    order_count = int(df[order_column].nunique(dropna=True))
                else:
                    order_count = len(df)
                st.metric("Total orders", f"{order_count:,}")

                product_column = next(
                    (column for column in category_columns if "product" in str(column).lower()),
                    None,
                )
                if product_column is not None:
                    st.metric(
                        "Products", f"{int(df[product_column].nunique(dropna=True)):,} unique"
                    )

                # Display money/quantity fields as totals, but never total an ID.
                for preferred_name in ("sales", "profit"):
                    measure = next(
                        (
                            column
                            for column in measure_columns
                            if str(column).strip().lower() == preferred_name
                        ),
                        None,
                    )
                    if measure is not None:
                        st.metric(
                            f"Total {measure}",
                            f"{df[measure].sum():,.2f}".rstrip("0").rstrip("."),
                        )

                # Highlight the best product using profit where available,
                # otherwise use sales as the ranking measure.
                if product_column is not None:
                    ranking_measure = next(
                        (
                            column
                            for preferred_name in ("profit", "sales")
                            for column in measure_columns
                            if str(column).strip().lower() == preferred_name
                        ),
                        None,
                    )
                    if ranking_measure is not None:
                        product_totals = df.groupby(
                            product_column, dropna=False
                        )[ranking_measure].sum()
                        if not product_totals.empty:
                            st.caption(
                                f"Top {product_column} by {ranking_measure}: "
                                f"**{product_totals.idxmax()}** "
                                f"({product_totals.max():,.2f})"
                            )

                if not measure_columns:
                    st.info("No numeric measures are available for totals.")

    # Natural-language Q&A, routed through the safe analytics agent.
    with assistant_col:
        with st.container(border=True):
            st.subheader("AI analytics agent")
            st.caption("Ask questions about your data in natural language.")
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            for entry in st.session_state.chat_history[-4:]:
                with st.chat_message("user"):
                    st.write(entry["question"])
                with st.chat_message("assistant"):
                    show_answer(entry["answer"])

            if not st.session_state.chat_history:
                with st.chat_message("assistant"):
                    st.write("Try: **What is the total Sales by Region?**")

            question = st.chat_input("Ask a question...")
            if question:
                answer = analyze_question(df, question, graph=graph)
                st.session_state.chat_history.append(
                    {"question": question, "answer": answer}
                )
                st.rerun()

            if not st.session_state.chat_history:
                suggestions = {
                    "Show missing values": "show missing values",
                    "Summarize numeric data": "summarize numeric data",
                }
                numeric_columns = df.select_dtypes(include="number").columns
                if len(numeric_columns):
                    metric = numeric_columns[0]
                    category_columns = df.select_dtypes(
                        include=["object", "category", "string"]
                    ).columns
                    if len(category_columns):
                        suggestions["Sales by category"] = (
                            f"total {metric} by {category_columns[0]}"
                        )
                    else:
                        suggestions[f"Total {metric}"] = f"total {metric}"

                selected_suggestion = st.pills(
                    "Try asking",
                    list(suggestions),
                    label_visibility="collapsed",
                    key="question_suggestion",
                )
                if selected_suggestion:
                    prompt = suggestions[selected_suggestion]
                    answer = analyze_question(df, prompt, graph=graph)
                    st.session_state.chat_history.append(
                        {"question": prompt, "answer": answer}
                    )
                    st.rerun()

# -----------------------------------------------------------------------------
# 7. Dataset page
# Full uploaded data table, column profile, and numeric statistics.
# -----------------------------------------------------------------------------
elif page == "Dataset":
    preview_tab, profile_tab = st.tabs(["Dataset preview", "Data profile"])
    with preview_tab:
        st.dataframe(df, hide_index=True, alt=f"All rows in {dataset_name}")
    with profile_tab:
        profile = pd.DataFrame(
            {
                "Column": summary["column_names"],
                "Data type": [summary["data_types"][c] for c in summary["column_names"]],
                "Missing values": [summary["missing_values"][c] for c in summary["column_names"]],
                "Unique values": [int(df[c].nunique()) for c in summary["column_names"]],
            }
        )
        st.dataframe(profile, hide_index=True, alt="Dataset profile by column")
        numeric_summary = df.describe(include="number")
        if numeric_summary.empty:
            st.info("No numeric columns are available for statistical summaries.")
        else:
            st.subheader("Numeric summary")
            st.dataframe(numeric_summary, alt="Statistics for numeric dataset columns")

# -----------------------------------------------------------------------------
# 8. Knowledge graph page
# Graph visualization plus inspectable node and relationship tables.
# -----------------------------------------------------------------------------
elif page == "Knowledge graph":
    node_col, edge_col = st.columns(2)
    node_col.metric("Graph nodes", graph_summary["node_count"], border=True)
    edge_col.metric("Relationships", graph_summary["edge_count"], border=True)
    st.graphviz_chart(
        make_graphviz_source(graph),
        alt="Schema graph connecting the dataset and its columns",
    )
    nodes_tab, edges_tab = st.tabs(["Nodes", "Relationships"])
    with nodes_tab:
        st.dataframe(pd.DataFrame(graph_summary["nodes"]), hide_index=True, alt="Graph nodes and metadata")
    with edges_tab:
        st.dataframe(pd.DataFrame(graph_summary["edges"]), hide_index=True, alt="Graph relationships")

# -----------------------------------------------------------------------------
# 9. Analytics agent page
# A focused question interface for the uploaded dataset.
# -----------------------------------------------------------------------------
elif page == "Analytics agent":
    st.subheader("Ask your data")
    st.caption("Ask a question using a numeric column, such as Sales or Profit.")
    question = st.chat_input("Ask a question about this dataset...")
    if question:
        answer = analyze_question(df, question, graph=graph)
        show_answer(answer)

# -----------------------------------------------------------------------------
# 10. Chat history page
# Review previous questions and results, or clear the conversation.
# -----------------------------------------------------------------------------
else:
    st.subheader("Chat history")
    history = st.session_state.get("chat_history", [])
    if not history:
        st.info("Your questions and analysis results will appear here.")
    else:
        for entry in history:
            with st.chat_message("user"):
                st.write(entry["question"])
            with st.chat_message("assistant"):
                show_answer(entry["answer"])
        if st.button("Clear chat history", icon=":material/delete:"):
            st.session_state.chat_history = []
            st.rerun()
