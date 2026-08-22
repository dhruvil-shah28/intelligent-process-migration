#!/usr/bin/env python3

import json


VALID_MESSAGES = {
    "NODE_REGISTER",
    "NODE_STATUS",
    "PROCESS_LIST",
    "PING",
}


def encode(message):
    """Encode a protocol message as newline-delimited JSON."""
    return (json.dumps(message, separators=(",", ":")) + "\n").encode()


def decode(line):
    """Decode one newline-delimited JSON message."""
    message = json.loads(line)

    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")

    message_type = message.get("type")

    if message_type not in VALID_MESSAGES:
        raise ValueError(f"unsupported message type: {message_type}")

    return message
