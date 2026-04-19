"""Quick Cypher runner. Usage: python query.py "MATCH (n) RETURN count(n)"""""
import os
import sys

from neo4j import GraphDatabase


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: query.py <cypher>", file=sys.stderr)
        sys.exit(2)
    cypher = sys.argv[1]
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    try:
        with driver.session() as s:
            for r in s.run(cypher):
                print(dict(r))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
