#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import socket
import struct
import tarfile
import time
from datetime import datetime, timezone


HEADER_SIZE = 8
BUFFER_SIZE = 1024 * 1024


def send_json(sock, message):
    data = json.dumps(
        message,
        separators=(",", ":"),
    ).encode()

    sock.sendall(
        struct.pack("!Q", len(data))
    )

    sock.sendall(data)


def recv_exact(sock, size):
    chunks = []
    remaining = size

    while remaining:
        chunk = sock.recv(
            min(BUFFER_SIZE, remaining)
        )

        if not chunk:
            raise ConnectionError(
                "connection closed during transfer"
            )

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def recv_json(sock):
    raw_size = recv_exact(
        sock,
        HEADER_SIZE,
    )

    size = struct.unpack(
        "!Q",
        raw_size,
    )[0]

    if size > 1024 * 1024:
        raise ValueError(
            "control message too large"
        )

    return json.loads(
        recv_exact(sock, size)
    )


def sha256_file(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        while True:
            chunk = file.read(BUFFER_SIZE)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def create_archive(source_dir, archive_path):
    """
    Create a gzip-compressed archive of a checkpoint directory.
    """

    source_dir = os.path.abspath(source_dir)
    archive_path = os.path.abspath(archive_path)

    with tarfile.open(
        archive_path,
        "w:gz",
    ) as archive:
        archive.add(
            source_dir,
            arcname=os.path.basename(source_dir),
        )

    return {
        "archive": archive_path,
        "size_bytes": os.path.getsize(
            archive_path
        ),
        "sha256": sha256_file(
            archive_path
        ),
    }


def safe_extract(archive_path, destination):
    """
    Extract an archive while preventing path traversal.
    """

    destination = os.path.abspath(destination)

    with tarfile.open(
        archive_path,
        "r:gz",
    ) as archive:

        for member in archive.getmembers():

            target = os.path.abspath(
                os.path.join(
                    destination,
                    member.name,
                )
            )

            if not (
                target == destination
                or target.startswith(
                    destination + os.sep
                )
            ):
                raise ValueError(
                    f"unsafe archive path: {member.name}"
                )

        archive.extractall(destination)


def receive_checkpoint(
    connection,
    address,
    destination_dir,
):
    """
    Receive a checkpoint archive over an existing TCP connection.
    """

    os.makedirs(
        destination_dir,
        exist_ok=True,
    )

    sock = connection

    metadata = recv_json(sock)

    if metadata.get("type") != "CHECKPOINT_TRANSFER":
        raise ValueError(
            "invalid transfer type"
        )

    archive_size = metadata["size_bytes"]
    expected_sha256 = metadata["sha256"]

    if archive_size <= 0:
        raise ValueError(
            "invalid archive size"
        )

    archive_path = os.path.join(
        destination_dir,
        "checkpoint-transfer.tar.gz",
    )

    received = 0

    with open(
        archive_path,
        "wb",
    ) as output:

        while received < archive_size:

            chunk = sock.recv(
                min(
                    BUFFER_SIZE,
                    archive_size - received,
                )
            )

            if not chunk:
                raise ConnectionError(
                    "connection closed during checkpoint transfer"
                )

            output.write(chunk)
            received += len(chunk)

    actual_sha256 = sha256_file(
        archive_path
    )

    if actual_sha256 != expected_sha256:

        os.remove(archive_path)

        raise ValueError(
            "checkpoint checksum mismatch"
        )

    extract_dir = os.path.join(
        destination_dir,
        "received",
    )

    os.makedirs(
        extract_dir,
        exist_ok=True,
    )

    safe_extract(
        archive_path,
        extract_dir,
    )

    return {
        "type": "CHECKPOINT_RECEIVED",
        "source_address": str(address),
        "size_bytes": archive_size,
        "sha256": actual_sha256,
        "archive": archive_path,
        "extract_dir": extract_dir,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def serve(host, port, destination_dir):
    """
    Start the Node B checkpoint transfer server.
    """

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )

    server.bind(
        (host, port)
    )

    server.listen(5)

    print(
        json.dumps(
            {
                "event": "transfer_server_started",
                "host": host,
                "port": port,
                "destination": destination_dir,
            }
        ),
        flush=True,
    )

    try:

        while True:

            connection, address = server.accept()

            try:

                result = receive_checkpoint(
                    connection,
                    address,
                    destination_dir,
                )

                send_json(
                    connection,
                    result,
                )

                print(
                    json.dumps(result),
                    flush=True,
                )

            except Exception as exc:

                error = {
                    "type": "TRANSFER_ERROR",
                    "error": str(exc),
                }

                try:
                    send_json(
                        connection,
                        error,
                    )
                except Exception:
                    pass

                print(
                    json.dumps(error),
                    flush=True,
                )

            finally:

                connection.close()

    except KeyboardInterrupt:

        print(
            json.dumps(
                {
                    "event": "transfer_server_stopped",
                }
            ),
            flush=True,
        )

    finally:

        server.close()


def send_checkpoint(
    host,
    port,
    archive_path,
):
    """
    Send a checkpoint archive to a remote Node Agent.
    """

    archive_path = os.path.abspath(
        archive_path
    )

    if not os.path.isfile(archive_path):
        raise FileNotFoundError(
            archive_path
        )

    size_bytes = os.path.getsize(
        archive_path
    )

    sha256 = sha256_file(
        archive_path
    )

    metadata = {
        "type": "CHECKPOINT_TRANSFER",
        "filename": os.path.basename(
            archive_path
        ),
        "size_bytes": size_bytes,
        "sha256": sha256,
    }

    started = time.monotonic()

    with socket.create_connection(
        (host, port),
        timeout=10,
    ) as sock:

        send_json(
            sock,
            metadata,
        )

        sent = 0

        with open(
            archive_path,
            "rb",
        ) as file:

            while True:

                chunk = file.read(
                    BUFFER_SIZE
                )

                if not chunk:
                    break

                sock.sendall(chunk)
                sent += len(chunk)

        response = recv_json(sock)

    elapsed = (
        time.monotonic()
        - started
    )

    response["transfer_time_seconds"] = round(
        elapsed,
        6,
    )

    response["transfer_rate_mbps"] = round(
        (
            size_bytes * 8
            / elapsed
            / 1_000_000
        )
        if elapsed > 0
        else 0.0,
        3,
    )

    response["bytes_sent"] = sent

    return response


def main():
    parser = argparse.ArgumentParser(
        description="Checkpoint transfer utility"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    serve_parser = subparsers.add_parser(
        "serve"
    )

    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
    )

    serve_parser.add_argument(
        "--port",
        type=int,
        required=True,
    )

    serve_parser.add_argument(
        "--destination",
        required=True,
    )

    send_parser = subparsers.add_parser(
        "send"
    )

    send_parser.add_argument(
        "--host",
        required=True,
    )

    send_parser.add_argument(
        "--port",
        type=int,
        required=True,
    )

    send_parser.add_argument(
        "--archive",
        required=True,
    )

    archive_parser = subparsers.add_parser(
        "archive"
    )

    archive_parser.add_argument(
        "--source",
        required=True,
    )

    archive_parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    if args.command == "serve":

        serve(
            args.host,
            args.port,
            args.destination,
        )

    elif args.command == "archive":

        result = create_archive(
            args.source,
            args.output,
        )

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

    elif args.command == "send":

        result = send_checkpoint(
            args.host,
            args.port,
            args.archive,
        )

        print(
            json.dumps(
                result,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
