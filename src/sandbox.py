"""Validate and run explicitly approved analytics operations.

This module deliberately does not evaluate Python expressions or execute
generated code. Callers provide an operation name and existing DataFrame
column names; only the operations in ``APPROVED_OPERATIONS`` can run.
"""

from collections.abc import Mapping
from typing import Any

import pandas as pd


APPROVED_OPERATIONS = frozenset(
	{
		"sum",
		"mean",
		"count",
		"min",
		"max",
		"summary",
		"missing_values",
		"duplicate_rows",
	}
)

_AGGREGATIONS = {
	"sum": "sum",
	"mean": "mean",
	"count": "count",
	"min": "min",
	"max": "max",
}


def validate_operation_request(
	frame: pd.DataFrame,
	operation: str,
	column: str | None = None,
	group_by: str | None = None,
) -> str:
	"""Validate an operation and its columns, returning normalized operation.

	Raises:
		TypeError: If the request arguments have invalid types.
		ValueError: If the operation or referenced columns are not permitted.
	"""
	if not isinstance(frame, pd.DataFrame):
		raise TypeError("Analytics input must be a pandas DataFrame.")
	if not isinstance(operation, str):
		raise TypeError("Operation must be a string.")

	normalized_operation = operation.strip().lower()
	if normalized_operation not in APPROVED_OPERATIONS:
		allowed = ", ".join(sorted(APPROVED_OPERATIONS))
		raise ValueError(f"Unsupported operation. Approved operations: {allowed}.")

	if frame.empty and normalized_operation not in {"summary", "missing_values", "duplicate_rows"}:
		raise ValueError("Cannot aggregate an empty dataset.")

	if normalized_operation in {"summary", "missing_values", "duplicate_rows"}:
		if column is not None or group_by is not None:
			raise ValueError(
				f"Operation '{normalized_operation}' does not accept a metric or grouping column."
			)
		return normalized_operation

	if not isinstance(column, str) or column not in frame.columns:
		raise ValueError("Choose a valid metric column from the dataset.")
	if not pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(
		frame[column]
	):
		raise ValueError(f"Column '{column}' must contain numeric values.")

	if group_by is not None:
		if not isinstance(group_by, str) or group_by not in frame.columns:
			raise ValueError("Choose a valid grouping column from the dataset.")
		if group_by == column:
			raise ValueError("The metric and grouping columns must be different.")

	return normalized_operation


def run_approved_operation(
	frame: pd.DataFrame,
	operation: str,
	column: str | None = None,
	group_by: str | None = None,
) -> Any:
	"""Execute one validated analytics operation on a DataFrame.

	Returns a scalar for a single-column aggregation, a dictionary for grouped
	or dataset-wide operations, and a nested dictionary for numeric summaries.
	"""
	operation = validate_operation_request(frame, operation, column, group_by)

	if operation == "summary":
		numeric_frame = frame.select_dtypes(include="number").drop(
			columns=[
				name
				for name in frame.columns
				if str(name).strip().lower() == "order_id"
			],
			errors="ignore",
		)
		if numeric_frame.empty:
			return {}
		return numeric_frame.describe().to_dict()

	if operation == "missing_values":
		return frame.isna().sum().astype(int).to_dict()

	if operation == "duplicate_rows":
		return int(frame.duplicated().sum())

	if column is None:
		# Validation guarantees a metric for aggregate operations.
		raise ValueError("A metric column is required for this operation.")

	if group_by is not None:
		grouped = frame.groupby(group_by, dropna=False)[column]
		result = grouped.agg(_AGGREGATIONS[operation])
		result = result.sort_values(ascending=operation == "min")
		return result.to_dict()

	values = frame[column].dropna()
	if values.empty:
		raise ValueError(f"Column '{column}' has no numeric values.")
	result = values.agg(_AGGREGATIONS[operation])
	if operation == "count":
		return int(result)
	return float(result)


def execute_request(frame: pd.DataFrame, request: Mapping[str, Any]) -> Any:
	"""Execute a mapping-based request after rejecting unknown request keys."""
	if not isinstance(request, Mapping):
		raise TypeError("Analytics request must be a mapping.")

	allowed_keys = {"operation", "column", "group_by"}
	unexpected_keys = set(request) - allowed_keys
	if unexpected_keys:
		raise ValueError(
			"Unexpected request fields: " + ", ".join(sorted(map(str, unexpected_keys)))
		)
	if "operation" not in request:
		raise ValueError("An operation is required.")

	return run_approved_operation(
		frame,
		operation=request["operation"],
		column=request.get("column"),
		group_by=request.get("group_by"),
	)
