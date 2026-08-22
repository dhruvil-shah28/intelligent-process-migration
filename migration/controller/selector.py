#!/usr/bin/env python3

from dataclasses import dataclass


@dataclass
class DestinationCandidate:
    node_id: str
    score: float
    cpu_pressure: float
    memory_pressure: float
    load_pressure: float
    available_memory_bytes: int


class DestinationSelector:
    """
    Select the least-loaded healthy destination node.

    Lower score = better destination.
    """

    def __init__(
        self,
        cpu_weight=0.45,
        memory_weight=0.30,
        load_weight=0.25,
    ):
        self.cpu_weight = cpu_weight
        self.memory_weight = memory_weight
        self.load_weight = load_weight

    @staticmethod
    def normalize(value, maximum):
        if maximum <= 0:
            return 1.0

        return min(max(value / maximum, 0.0), 1.0)

    def score_node(self, status):
        cpu = status.get("cpu_percent", 100.0)
        memory = status.get("memory_percent", 100.0)
        load = status.get("load_1m", 0.0)
        cores = max(status.get("cpu_cores", 1), 1)

        load_ratio = load / cores

        cpu_pressure = self.normalize(cpu, 100.0)
        memory_pressure = self.normalize(memory, 100.0)
        load_pressure = self.normalize(load_ratio, 1.0)

        score = (
            self.cpu_weight * cpu_pressure
            + self.memory_weight * memory_pressure
            + self.load_weight * load_pressure
        )

        return score, {
            "cpu_pressure": cpu_pressure,
            "memory_pressure": memory_pressure,
            "load_pressure": load_pressure,
            "available_memory_bytes": status.get(
                "memory_available_bytes",
                0,
            ),
        }

    def rank(self, node_statuses, exclude=None):
        """
        Rank available destination nodes.

        `exclude` prevents selecting the source node.
        """

        exclude = set(exclude or [])

        candidates = []

        for node_id, status in node_statuses.items():

            if node_id in exclude:
                continue

            if status.get("type") != "NODE_STATUS":
                continue

            score, pressures = self.score_node(status)

            candidates.append(
                DestinationCandidate(
                    node_id=node_id,
                    score=round(score, 4),
                    cpu_pressure=round(
                        pressures["cpu_pressure"],
                        4,
                    ),
                    memory_pressure=round(
                        pressures["memory_pressure"],
                        4,
                    ),
                    load_pressure=round(
                        pressures["load_pressure"],
                        4,
                    ),
                    available_memory_bytes=pressures[
                        "available_memory_bytes"
                    ],
                )
            )

        candidates.sort(key=lambda candidate: candidate.score)

        return candidates

    def select(self, node_statuses, exclude=None):
        ranked = self.rank(
            node_statuses,
            exclude=exclude,
        )

        if not ranked:
            raise RuntimeError(
                "no suitable destination nodes available"
            )

        return ranked[0]


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Destination selection engine"
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Source node ID",
    )

    parser.add_argument(
        "--status",
        required=True,
        help="JSON object containing node statuses",
    )

    args = parser.parse_args()

    statuses = json.loads(args.status)

    selector = DestinationSelector()

    ranked = selector.rank(
        statuses,
        exclude=[args.source],
    )

    print("===== DESTINATION RANKING =====")

    for index, candidate in enumerate(ranked, start=1):
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

    if ranked:
        print("===== SELECTED DESTINATION =====")
        print(ranked[0].node_id)


if __name__ == "__main__":
    main()
