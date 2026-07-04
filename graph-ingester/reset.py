"""One-shot wipe of all nodes + edges - DATA only. Schema (the
entity_name_unique constraint) survives; ingest.py's ensure_schema
recreates it anyway. Next scheduled ingest repopulates from scratch."""
import os

from neo4j import GraphDatabase


def main() -> None:
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    try:
        with driver.session() as s:
            before = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
            s.run("MATCH (n) DETACH DELETE n")
            after = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        print(f"[reset] before={before} after={after}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
