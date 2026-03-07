"""Sprint 1: Verify Memgraph connection on localhost:7687."""
import sys
import mgclient


def main():
    try:
        conn = mgclient.connect(host="127.0.0.1", port=7687, username="admin", password="admin")
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    cursor = conn.cursor()
    cursor.execute("RETURN 'stream-graph-rag is live' AS status")
    row = cursor.fetchone()
    print(f"status: {row[0]}")
    conn.close()


if __name__ == "__main__":
    main()
