"""Sprint 1: Minimal Pathway pipeline — confirms Pathway is installed and running."""
import pathway as pw


def main():
    # Static in-memory source: 3 rows
    import pandas as pd

    df = pd.DataFrame({
        "id": [1, 2, 3],
        "message": [
            "hello from Pathway",
            "stream-graph-rag Sprint 1",
            "Pathway is running correctly",
        ],
    })
    table = pw.debug.table_from_pandas(df)
    pw.debug.compute_and_print(table)


if __name__ == "__main__":
    main()
