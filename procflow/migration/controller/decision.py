#!/usr/bin/env python3

import argparse
import json
import psutil


DEFAULT_WEIGHTS = {
    "cpu": 0.55,
    "memory": 0.20,
    "load": 0.25,
    "migration_cost": 0.15,
}


DEFAULT_THRESHOLDS = {
    "cpu": 80.0,
    "memory": 80.0,
    "load_ratio": 0.80,
    "migration_cost": 80.0,

    # Decision boundaries
    "monitor": 0.50,
    "migrate": 0.75,
}


def normalize(value, threshold):
    """Convert a metric into a bounded 0.0-1.0 pressure value."""

    if threshold <= 0:
        raise ValueError("threshold must be greater than zero")

    return min(max(value / threshold, 0.0), 1.0)


def calculate_pressures(metrics, thresholds=None):
    """Calculate normalized resource-pressure components."""

    thresholds = thresholds or DEFAULT_THRESHOLDS

    cpu_pressure = normalize(
        metrics["cpu_percent"],
        thresholds["cpu"],
    )

    memory_pressure = normalize(
        metrics["memory_percent"],
        thresholds["memory"],
    )

    cpu_cores = metrics.get(
        "cpu_cores",
        psutil.cpu_count(logical=True) or 1,
    )

    load_ratio = metrics["system_load_1m"] / cpu_cores

    load_pressure = normalize(
        load_ratio,
        thresholds["load_ratio"],
    )

    migration_cost_pressure = normalize(
        metrics.get("migration_cost_percent", 0.0),
        thresholds["migration_cost"],
    )

    return {
        "cpu_pressure": cpu_pressure,
        "memory_pressure": memory_pressure,
        "load_pressure": load_pressure,
        "migration_cost_pressure": migration_cost_pressure,
        "load_ratio": load_ratio,
        "cpu_cores": cpu_cores,
    }


def calculate_score(metrics, weights=None, thresholds=None):
    """
    Calculate the migration pressure score.

    The migration cost acts as a penalty rather than a positive
    contribution to migration pressure.
    """

    weights = weights or DEFAULT_WEIGHTS

    pressures = calculate_pressures(
        metrics,
        thresholds=thresholds,
    )

    base_score = (
        weights["cpu"] * pressures["cpu_pressure"]
        + weights["memory"] * pressures["memory_pressure"]
        + weights["load"] * pressures["load_pressure"]
    )

    cost_penalty = (
        weights["migration_cost"]
        * pressures["migration_cost_pressure"]
    )

    score = base_score - cost_penalty

    return min(max(score, 0.0), 1.0), pressures


def classify(score, thresholds=None):
    """Convert a migration score into an action."""

    thresholds = thresholds or DEFAULT_THRESHOLDS

    if score >= thresholds["migrate"]:
        return "MIGRATE"

    if score >= thresholds["monitor"]:
        return "MONITOR"

    return "NORMAL"


def evaluate(metrics, weights=None, thresholds=None):
    """Return an explainable migration decision."""

    weights = weights or DEFAULT_WEIGHTS
    thresholds = thresholds or DEFAULT_THRESHOLDS

    score, pressures = calculate_score(
        metrics,
        weights=weights,
        thresholds=thresholds,
    )

    action = classify(
        score,
        thresholds=thresholds,
    )

    return {
        "pid": metrics.get("pid"),
        "score": round(score, 4),
        "action": action,

        "pressures": {
            "cpu": round(
                pressures["cpu_pressure"],
                4,
            ),
            "memory": round(
                pressures["memory_pressure"],
                4,
            ),
            "load": round(
                pressures["load_pressure"],
                4,
            ),
            "migration_cost": round(
                pressures["migration_cost_pressure"],
                4,
            ),
        },

        "system": {
            "cpu_cores": pressures["cpu_cores"],
            "load_ratio": round(
                pressures["load_ratio"],
                4,
            ),
        },

        "inputs": {
            "cpu_percent": metrics["cpu_percent"],
            "memory_percent": metrics["memory_percent"],
            "system_load_1m": metrics["system_load_1m"],
            "migration_cost_percent": metrics.get(
                "migration_cost_percent",
                0.0,
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Intelligent Process Migration decision engine"
    )

    parser.add_argument(
        "--metrics",
        required=True,
        help="JSON object containing resource metrics",
    )

    args = parser.parse_args()

    try:
        metrics = json.loads(args.metrics)
    except json.JSONDecodeError as exc:
        parser.error(f"invalid metrics JSON: {exc}")

    required = {
        "cpu_percent",
        "memory_percent",
        "system_load_1m",
    }

    missing = required - metrics.keys()

    if missing:
        parser.error(
            "missing required metrics: "
            + ", ".join(sorted(missing))
        )

    print(
        json.dumps(
            evaluate(metrics),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
