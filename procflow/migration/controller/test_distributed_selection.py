#!/usr/bin/env python3

import json

from migration.controller.node_manager import NodeManager
from migration.controller.selector import DestinationSelector


def main():
    manager = NodeManager()

    print("===== REGISTERING NODES =====")

    manager.register_remote(
        "node-a",
        "127.0.0.1",
        5001,
    )

    manager.register_remote(
        "node-b",
        "127.0.0.1",
        5002,
    )

    print("node-a: REGISTERED")
    print("node-b: REGISTERED")

    print()
    print("===== COLLECTING NODE STATUS =====")

    statuses = manager.get_all_status()

    print(
        json.dumps(
            statuses,
            indent=2,
        )
    )

    print()
    print("===== DESTINATION RANKING =====")

    selector = DestinationSelector()

    ranked = selector.rank(
        statuses,
        exclude=["node-a"],
    )

    for index, candidate in enumerate(
        ranked,
        start=1,
    ):
        print(
            json.dumps(
                {
                    "rank": index,
                    "node_id": candidate.node_id,
                    "score": candidate.score,
                    "cpu_pressure": candidate.cpu_pressure,
                    "memory_pressure": candidate.memory_pressure,
                    "load_pressure": candidate.load_pressure,
                    "available_memory_bytes": (
                        candidate.available_memory_bytes
                    ),
                },
                indent=2,
            )
        )

    if not ranked:
        raise SystemExit(
            "[ERROR] No destination available."
        )

    selected = ranked[0]

    print()
    print("===== SELECTED DESTINATION =====")
    print(f"Source      : node-a")
    print(f"Destination : {selected.node_id}")
    print(f"Score       : {selected.score:.4f}")

    print()
    print("[OK] Distributed destination selection successful.")


if __name__ == "__main__":
    main()
