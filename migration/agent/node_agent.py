#!/usr/bin/env python3

import argparse
import json
import socket
import socketserver
import time
from datetime import datetime, timezone

import psutil

from migration.agent.protocol import decode, encode


class NodeAgent:
    """Resource-monitoring agent for one migration node."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.hostname = socket.gethostname()

    def node_status(self):
        """Return current node-level resource information."""

        memory = psutil.virtual_memory()

        return {
            "type": "NODE_STATUS",
            "node_id": self.node_id,
            "hostname": self.hostname,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": memory.percent,
            "memory_available_bytes": memory.available,
            "load_1m": psutil.getloadavg()[0],
            "cpu_cores": psutil.cpu_count(logical=True) or 1,
            "process_count": len(psutil.pids()),
        }

    def process_list(self):
        """Return controlled process metadata for the node."""

        processes = []

        for process in psutil.process_iter(
            ["pid", "name", "status", "username"]
        ):
            try:
                info = process.info

                processes.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"],
                        "status": info["status"],
                        "username": info["username"],
                    }
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        return {
            "type": "PROCESS_LIST",
            "node_id": self.node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "processes": processes,
        }

    def handle(self, message):
        """Handle one controller request."""

        message_type = message["type"]

        if message_type == "PING":
            return {
                "type": "PONG",
                "node_id": self.node_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if message_type == "NODE_REGISTER":
            return {
                "type": "NODE_REGISTER",
                "node_id": self.node_id,
                "hostname": self.hostname,
                "capabilities": {
                    "resource_monitoring": True,
                    "process_discovery": True,
                    "checkpoint_restore": True,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if message_type == "NODE_STATUS":
            return self.node_status()

        if message_type == "PROCESS_LIST":
            return self.process_list()

        raise ValueError(
            f"unsupported message type: {message_type}"
        )


class RequestHandler(socketserver.StreamRequestHandler):

    def handle(self):
        agent = self.server.agent

        while True:
            line = self.rfile.readline()

            if not line:
                break

            try:
                message = decode(line)
                response = agent.handle(message)

            except Exception as exc:
                response = {
                    "type": "ERROR",
                    "error": str(exc),
                }

            self.wfile.write(encode(response))
            self.wfile.flush()


class ThreadedNodeServer(
    socketserver.ThreadingMixIn,
    socketserver.TCPServer,
):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(
        description="Intelligent Process Migration Node Agent"
    )

    parser.add_argument(
        "--node-id",
        required=True,
        help="Unique node identifier",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address",
    )

    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="TCP port",
    )

    args = parser.parse_args()

    agent = NodeAgent(args.node_id)

    server = ThreadedNodeServer(
        (args.host, args.port),
        RequestHandler,
    )

    server.agent = agent

    print(
        json.dumps(
            {
                "event": "node_agent_started",
                "node_id": args.node_id,
                "hostname": agent.hostname,
                "host": args.host,
                "port": args.port,
            }
        ),
        flush=True,
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "event": "node_agent_stopped",
                    "node_id": args.node_id,
                }
            ),
            flush=True,
        )

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
