
import networkx as nx
import pandas as pd


def build_schema_graph(df, dataset_name="Uploaded Dataset"):
    """Build a knowledge graph from a DataFrame schema."""

    graph = nx.DiGraph()

    # Dataset node
    graph.add_node(
        dataset_name,
        node_type="dataset",
        row_count=len(df),
        column_count=len(df.columns),
    )

    # Column nodes and their metadata
    for column in df.columns:
        series = df[column]

        graph.add_node(
            column,
            node_type="column",
            data_type=str(series.dtype),
            missing_count=int(series.isna().sum()),
            unique_count=int(series.nunique()),
            sample_values=[
                str(value)
                for value in series.dropna().unique()[:5]
            ],
        )

        graph.add_edge(
            dataset_name,
            column,
            relation="HAS_COLUMN",
        )

    # Identify columns with matching names as a
    # preliminary candidate for possible relationships.
    # Actual business relationships need validation.
    for column in df.columns:
        normalized = str(column).strip().lower()

        if normalized.endswith("_id"):
            graph.nodes[column]["possible_key"] = True
        else:
            graph.nodes[column]["possible_key"] = False

    return graph


def get_graph_summary(graph):
    """Return a simple, readable graph summary."""

    nodes = []

    for node, attributes in graph.nodes(data=True):
        nodes.append({
            "name": node,
            **attributes,
        })

    edges = [
        {
            "source": source,
            "target": target,
            **attributes,
        }
        for source, target, attributes in graph.edges(data=True)
    ]

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "nodes": nodes,
        "edges": edges,
    }
