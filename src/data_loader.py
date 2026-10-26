
import pandas as pd


def load_dataset(uploaded_file):
    """Load and validate a CSV or Excel dataset."""

    if uploaded_file is None:
        raise ValueError("Please upload a dataset.")

    filename = uploaded_file.name.lower()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(uploaded_file)

        elif filename.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file, engine="openpyxl")

        else:
            raise ValueError(
                "Unsupported file format. Upload CSV or XLSX."
            )

    except (ValueError, UnicodeDecodeError):
        raise
    except Exception as exc:
        raise ValueError(
            f"Could not read the dataset: {exc}"
        ) from exc

    if df.empty:
        raise ValueError("The uploaded dataset is empty.")

    if len(df.columns) == 0:
        raise ValueError("The dataset has no columns.")

    # Clean column names
    df.columns = [
        str(column).strip() for column in df.columns
    ]

    if any(not column for column in df.columns):
        raise ValueError("Column names cannot be empty.")

    if df.columns.duplicated().any():
        raise ValueError(
            "Duplicate column names found. Please rename them."
        )

    return df


def get_dataset_summary(df):
    """Return basic metadata about the dataset."""

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
        "data_types": {
            column: str(dtype)
            for column, dtype in df.dtypes.items()
        },
        "missing_values": {
            column: int(count)
            for column, count in df.isnull().sum().items()
        },
        "duplicate_rows": int(df.duplicated().sum()),
    }
