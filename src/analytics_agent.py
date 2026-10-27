
import re
import pandas as pd

from src.sandbox import run_approved_operation


def find_column(df, text):
    """Find a column mentioned in the user's question."""

    text = text.lower()

    # Match longer column names first
    columns = sorted(
        df.columns,
        key=lambda col: len(str(col)),
        reverse=True,
    )

    for column in columns:
        name = str(column).strip().lower()

        if re.search(
            r"(?<!\w)" + re.escape(name) + r"(?!\w)",
            text,
        ):
            return column

    return None


def analyze_question(df, question, graph=None):
    """
    Analyze a dataset using predefined analytical operations.
    No generated code or eval() is executed.
    """

    if df.empty:
        return {"status": "error", "message": "Dataset is empty."}

    question = question.strip().lower()

    if not question:
        return {
            "status": "error",
            "message": "Please enter a question.",
        }

    # Use graph metadata when provided
    if graph is not None:
        graph_columns = [
            node
            for node, attrs in graph.nodes(data=True)
            if attrs.get("node_type") == "column"
        ]
        available_columns = [
            col for col in df.columns if col in graph_columns
        ]
    else:
        available_columns = list(df.columns)

    if not available_columns:
        return {
            "status": "error",
            "message": "No matching dataset columns found in the graph.",
        }

    numeric_columns = [
        col for col in available_columns
        if pd.api.types.is_numeric_dtype(df[col])
        and not pd.api.types.is_bool_dtype(df[col])
    ]

    # Identify a column explicitly mentioned in the question
    metric = find_column(df[numeric_columns], question) \
        if numeric_columns else None

    # Detect common metric aliases
    if metric is None and numeric_columns:
        aliases = {
            "revenue": ["revenue", "sales", "amount"],
            "income": ["income", "revenue", "sales"],
            "quantity": ["quantity", "qty", "units"],
        }

        for keyword, candidates in aliases.items():
            if keyword in question:
                for candidate in candidates:
                    metric = next(
                        (
                            col for col in numeric_columns
                            if str(col).lower() == candidate
                        ),
                        None,
                    )
                    if metric is not None:
                        break
            if metric is not None:
                break

    # Infer the operation
    if any(word in question for word in
           ["missing", "null", "empty values"]):
        return {
            "status": "success",
            "operation": "missing_values",
            "result": run_approved_operation(df, "missing_values"),
        }

    if any(word in question for word in
           ["duplicate", "duplicates"]):
        return {
            "status": "success",
            "operation": "duplicate_rows",
            "result": run_approved_operation(df, "duplicate_rows"),
        }

    if any(word in question for word in
           ["describe", "summary", "statistics", "statistical"]):
        return {
            "status": "success",
            "operation": "summary",
            "result": run_approved_operation(df, "summary"),
        }

    if metric is None:
        return {
            "status": "needs_clarification",
            "message": (
                "Please mention a numeric column, such as Sales or Profit, "
                "or ask for missing values, duplicates, or a dataset summary."
            ),
        }

    # Find a grouping column, e.g. "sales by region"
    group_column = None

    for column in available_columns:
        if column == metric:
            continue

        name = str(column).strip().lower()

        if re.search(
            r"\b(by|per|for each|grouped by)\s+"
            + re.escape(name)
            + r"\b",
            question,
        ):
            group_column = column
            break

    # Aggregation intent
    if any(word in question for word in
           ["average", "average of", "mean"]):
        operation = "mean"
    elif any(word in question for word in
             ["count", "number of"]):
        operation = "count"
    elif any(word in question for word in
             ["highest", "maximum", "max", "largest", "top"]):
        operation = "max"
    elif any(word in question for word in
             ["lowest", "minimum", "min", "smallest"]):
        operation = "min"
    else:
        operation = "sum"

    # Execute grouped and single-column aggregates through the operation
    # sandbox so analytics are validated against the approved operation list.
    if group_column is not None:
        try:
            result = run_approved_operation(
                df,
                operation,
                column=metric,
                group_by=group_column,
            )
        except (TypeError, ValueError) as error:
            return {"status": "error", "message": str(error)}

        return {
            "status": "success",
            "operation": operation,
            "metric": str(metric),
            "group_by": str(group_column),
            "result": result,
        }

    # Single-column aggregation.
    try:
        result = run_approved_operation(df, operation, column=metric)
    except (TypeError, ValueError) as error:
        return {"status": "error", "message": str(error)}

    return {
        "status": "success",
        "operation": operation,
        "metric": str(metric),
        "result": result,
    }
