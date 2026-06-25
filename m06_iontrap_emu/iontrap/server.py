"""
M06 ex06 — asyncio TCP/JSON Experiment Server
==============================================
A minimal asyncio TCP server that accepts JSON-encoded experiment requests
and returns JSON-encoded results.

Protocol
--------
Client sends a newline-terminated JSON object:
  {"cmd": "<command>", "params": {...}}

Server responds with newline-terminated JSON:
  {"ok": true,  "result": {...}}   on success
  {"ok": false, "error": "..."}   on failure

Supported commands
-------------------
rabi_scan        — carrier Rabi oscillation vs pulse duration
sideband_cooling — sideband cooling to target n_bar
readout          — sample photon counts + discrimination
ms_gate          — MS gate Bell-state fidelity

Usage
-----
  python -m iontrap.server &        # start server on localhost:7777

  echo '{"cmd":"rabi_scan","params":{"n_points":5}}' | nc localhost 7777

Interview note: ARTIQ's real-time experiment scheduling uses asyncio
(experiment.run() is called inside an asyncio event loop by artiq.dashboard.
Understanding async/await is essential for writing ARTIQ experiments that
coordinate multiple parallel experiments or instrument services.)

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import sys

import numpy as np

from .ion     import IonTrap
from .cooling import SidebandCooling, sideband_cooling_analytic
from .readout import FluorescenceReadout
from .ms_gate import MSGate, ms_fidelity_analytic

HOST = "127.0.0.1"
PORT = 7777

log = logging.getLogger("iontrap.server")


# ── Command handlers ──────────────────────────────────────────────────────────

def _handle_rabi_scan(params: dict) -> dict:
    """
    Carrier Rabi scan over pulse duration.

    params: n_points, n_bar, Omega_R_hz (optional)
    """
    n_points = int(params.get("n_points", 20))
    n_bar    = float(params.get("n_bar", 0.0))
    Omega_R  = 2 * math.pi * float(params.get("Omega_R_hz", 50e3))
    ion      = IonTrap(Omega_R=Omega_R, N_fock=10)
    t_pi     = ion.pi_time()
    t_list   = np.linspace(0, 2 * t_pi, n_points)
    p_e      = ion.evolve_carrier(t_list, n_bar=n_bar)
    return {
        "t_us": (t_list * 1e6).tolist(),
        "p_excited": p_e.tolist(),
        "t_pi_us": t_pi * 1e6,
    }


def _handle_sideband_cooling(params: dict) -> dict:
    """
    Analytic sideband cooling.

    params: n_bar_0, n_cycles
    """
    n_bar_0  = float(params.get("n_bar_0", 10.0))
    n_cycles = int(params.get("n_cycles", 50))
    n_bar_f  = sideband_cooling_analytic(n_bar_0, n_cycles)
    return {"n_bar_initial": n_bar_0, "n_cycles": n_cycles, "n_bar_final": n_bar_f}


def _handle_readout(params: dict) -> dict:
    """
    Fluorescence readout for a given qubit state.

    params: state (0=bright, 1=dark), n_shots, mu_bright, mu_dark
    """
    state     = int(params.get("state", 0))
    n_shots   = int(params.get("n_shots", 100))
    mu_bright = float(params.get("mu_bright", 25.0))
    mu_dark   = float(params.get("mu_dark",   1.0))
    rd        = FluorescenceReadout(mu_bright, mu_dark)
    rng       = np.random.default_rng(0)
    counts    = rd.sample(state, n_shots, rng)
    threshold = rd.optimal_threshold()
    inferred  = rd.discriminate(counts, threshold)
    return {
        "mean_counts": float(counts.mean()),
        "threshold": threshold,
        "fidelity": float(np.mean(inferred == state)),
    }


def _handle_ms_gate(params: dict) -> dict:
    """
    Analytic MS gate fidelity.

    params: eta, n_bar
    """
    eta   = float(params.get("eta",   0.1))
    n_bar = float(params.get("n_bar", 0.0))
    F     = ms_fidelity_analytic(eta, n_bar)
    return {"eta": eta, "n_bar": n_bar, "fidelity": F}


HANDLERS = {
    "rabi_scan"        : _handle_rabi_scan,
    "sideband_cooling" : _handle_sideband_cooling,
    "readout"          : _handle_readout,
    "ms_gate"          : _handle_ms_gate,
}


# ── asyncio server ────────────────────────────────────────────────────────────

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle one client connection: read request, dispatch, send response."""
    peer = writer.get_extra_info("peername")
    log.debug("Connection from %s", peer)
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                req    = json.loads(line.decode())
                cmd    = req.get("cmd", "")
                params = req.get("params", {})
                if cmd not in HANDLERS:
                    raise ValueError(f"unknown command: {cmd!r}")
                result = HANDLERS[cmd](params)
                resp   = {"ok": True, "result": result}
            except Exception as exc:
                resp   = {"ok": False, "error": str(exc)}
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        log.debug("Connection from %s closed", peer)


async def run_server(host: str = HOST, port: int = PORT) -> None:
    srv = await asyncio.start_server(handle_client, host, port)
    async with srv:
        addrs = [str(s.getsockname()) for s in srv.sockets]
        log.info("IonTrap server listening on %s", addrs)
        await srv.serve_forever()


# ── Client helper for tests ───────────────────────────────────────────────────

async def send_request(cmd: str, params: dict, host: str = HOST, port: int = PORT) -> dict:
    """Send one JSON request and return the parsed response."""
    reader, writer = await asyncio.open_connection(host, port)
    payload = json.dumps({"cmd": cmd, "params": params}) + "\n"
    writer.write(payload.encode())
    await writer.drain()
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return json.loads(line.decode())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())
