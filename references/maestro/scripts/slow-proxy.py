#!/usr/bin/env python3
"""HTTP CONNECT proxy that can hold back client traffic, for widening race windows on a device.

`adb emu network delay` does not slow the emulator's Wi-Fi traffic, so slow-network-from-step.sh
points the emulator at this proxy instead. Traffic passes through untouched until the trigger file
exists; from then on every chunk the app sends is delayed, like a poor mobile connection.

Usage: slow-proxy.py <port> <trigger file> <delay seconds>
"""
import asyncio
import os
import sys

LISTEN_PORT = int(sys.argv[1])
TRIGGER_FILE = sys.argv[2]
DELAY_SECONDS = float(sys.argv[3])
CHUNK_SIZE = 65536


async def pipe(reader, writer, is_upstream):
    try:
        while True:
            data = await reader.read(CHUNK_SIZE)
            if not data:
                break
            if is_upstream and os.path.exists(TRIGGER_FILE):
                await asyncio.sleep(DELAY_SECONDS)
            writer.write(data)
            await writer.drain()
    except ConnectionError as error:
        print(f"connection closed: {error}", file=sys.stderr)
    except asyncio.CancelledError:
        pass
    finally:
        writer.close()


async def handle_client(client_reader, client_writer):
    request_line = await client_reader.readline()
    while (await client_reader.readline()) not in (b"\r\n", b"\n", b""):
        pass
    try:
        method, target, _ = request_line.decode("latin-1").split(" ", 2)
    except ValueError:
        print(f"malformed request line: {request_line!r}", file=sys.stderr)
        client_writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        client_writer.close()
        return
    if method != "CONNECT":
        client_writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
        client_writer.close()
        return
    try:
        host, port = target.rsplit(":", 1)
        server_reader, server_writer = await asyncio.open_connection(host, int(port))
    except (ValueError, OSError) as error:
        print(f"cannot reach {target}: {error}", file=sys.stderr)
        client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        client_writer.close()
        return
    client_writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
    await client_writer.drain()
    await asyncio.gather(
        pipe(client_reader, server_writer, is_upstream=True),
        pipe(server_reader, client_writer, is_upstream=False),
    )


async def main():
    # Loopback only: the Android emulator reaches the host's loopback as 10.0.2.2, and nothing else
    # on the network should be able to use this proxy.
    server = await asyncio.start_server(handle_client, "127.0.0.1", LISTEN_PORT)
    async with server:
        await server.serve_forever()


asyncio.run(main())
