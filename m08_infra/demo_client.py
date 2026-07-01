"""
M08 — docker-compose service demo client
=========================================
Connects to the M06 iontrap_emu asyncio TCP server (`iontrap-server` in
docker-compose.yml) and runs the same two requests M07's capstone stack
would issue against a *remote* physics backend.

WHY this exists instead of reusing m07_capstone/qpu/node.py directly:
node.py's QPUNode.connect() wires two Python objects together in the same
process (self._peer = other) — there is no network protocol to speak. The
one component in this repo that IS a real network service is M06's
iontrap.server (asyncio.start_server + JSON-over-TCP). So the honest
"capstone services" demo for compose is: run that server as its own
container, and hit it from a client container over the docker network —
exactly the client/server split a real multi-node deployment would have.

Usage (inside the `client` service, or manually):
    python demo_client.py --host iontrap-server --port 7777
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


async def send_request(host: str, port: int, cmd: str, params: dict, retries: int = 20) -> dict:
    """
    Open one connection, send one JSON request, return the parsed response.

    Retries with backoff because in compose the client container can start
    before the server's asyncio event loop has bound its listening socket.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            break
        except (ConnectionRefusedError, OSError) as exc:
            last_exc = exc
            await asyncio.sleep(0.5)
    else:
        raise ConnectionError(f"could not reach {host}:{port} after {retries} attempts") from last_exc

    payload = json.dumps({"cmd": cmd, "params": params}) + "\n"
    writer.write(payload.encode())
    await writer.drain()
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return json.loads(line.decode())


async def main(host: str, port: int) -> int:
    print(f"[client] connecting to iontrap-server at {host}:{port}")

    rabi = await send_request(host, port, "rabi_scan", {"n_points": 5})
    print(f"[client] rabi_scan  -> t_pi_us={rabi['result']['t_pi_us']:.3f}")

    ms = await send_request(host, port, "ms_gate", {"eta": 0.1, "n_bar": 0.05})
    print(f"[client] ms_gate    -> fidelity={ms['result']['fidelity']:.4f}")

    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="iontrap-server")
    ap.add_argument("--port", type=int, default=7777)
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.host, args.port)))
