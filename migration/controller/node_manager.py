#!/usr/bin/env python3

import json
import socket
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Node:
    node_id: str
    host: str
    port: int
    hostname: str | None = None
    status: dict | None = None
    last_seen: str | None = None


class NodeManager:
    """Maintain and query the distributed node registry."""

    def __init__(self, timeout=3.0):
        self.timeout = timeout
        self.nodes = {}

    def register(self, node_id, host, port):
        node = Node(
            node_id=node_id,
            host=host,
            port=port,
        )

        self.nodes[node_id] = node

        return node

    def _request(self, node, message):
        payload = (
            json.dumps(message, separators=(",", ":")) + "\n"
        ).encode()

        with socket.create_connection(
            (node.host, node.port),
            timeout=self.timeout,
        ) as sock:

            sock.sendall(payload)

            file = sock.makefile("r")
            line = file.readline()

        if not line:
            raise ConnectionError(
                f"node {node.node_id} returned no response"
            )

        response = json.loads(line)

        if response.get("type") == "ERROR":
            raise RuntimeError(response.get("error", "node error"))

        return response

    def register_remote(self, node_id, host, port):
        """Register a node and verify that it responds."""

        node = self.register(
            node_id=node_id,
            host=host,
            port=port,
        )

        response = self._request(
            node,
            {
                "type": "NODE_REGISTER",
            },
        )

        node.hostname = response.get("hostname")
        node.last_seen = datetime.now(
            timezone.utc
        ).isoformat()

        return response

    def get_status(self, node_id):
        node = self.nodes[node_id]

        response = self._request(
            node,
            {
                "type": "NODE_STATUS",
            },
        )

        node.status = response
        node.hostname = response.get("hostname")
        node.last_seen = datetime.now(
            timezone.utc
        ).isoformat()

        return response

    def get_all_status(self):
        results = {}

        for node_id in self.nodes:
            try:
                results[node_id] = self.get_status(node_id)

            except Exception as exc:
                results[node_id] = {
                    "type": "NODE_STATUS_ERROR",
                    "node_id": node_id,
                    "error": str(exc),
                }

        return results

    def get_processes(self, node_id):
        node = self.nodes[node_id]

        return self._request(
            node,
            {
                "type": "PROCESS_LIST",
            },
        )

    def healthy_nodes(self):
        """Return nodes that responded successfully."""

        healthy = []

        for node_id in self.nodes:
            try:
                self.get_status(node_id)
                healthy.append(self.nodes[node_id])

            except Exception:
                continue

        return healthy

    def summary(self):
        return {
            node_id: {
                "host": node.host,
                "port": node.port,
                "hostname": node.hostname,
                "status": node.status,
                "last_seen": node.last_seen,
            }
            for node_id, node in self.nodes.items()
        }


def main():
    manager = NodeManager()

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

    print("===== NODE REGISTRY =====")
    print(
        json.dumps(
            manager.summary(),
            indent=2,
        )
    )

    print("===== LIVE NODE STATUS =====")
    print(
        json.dumps(
            manager.get_all_status(),
            indent=2,
        )
    )

    print("===== HEALTHY NODES =====")
    print(
        json.dumps(
            [
                node.node_id
                for node in manager.healthy_nodes()
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
