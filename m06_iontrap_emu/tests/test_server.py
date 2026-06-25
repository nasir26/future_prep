"""
Tests for the asyncio TCP/JSON experiment server.
Author: Nasir Ali, C-DAC Noida
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import json
import math
import pytest

from iontrap.server import run_server, send_request, HOST, PORT

# ── Fixture: server that starts / stops around each test ─────────────────────

@pytest.fixture(scope="module")
def event_loop():
    """Module-scoped event loop (pytest-asyncio default is function-scoped)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def server(event_loop):
    """Start the server once for all tests in this module."""
    srv_task = event_loop.create_task(run_server(HOST, PORT))
    # Give the server time to bind
    event_loop.run_until_complete(asyncio.sleep(0.05))
    yield
    srv_task.cancel()
    try:
        event_loop.run_until_complete(srv_task)
    except (asyncio.CancelledError, Exception):
        pass


def _run(coro, loop):
    return loop.run_until_complete(coro)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestServerProtocol:

    def test_rabi_scan_ok(self, server, event_loop):
        """rabi_scan command returns ok=True with t_us and p_excited."""
        resp = _run(send_request("rabi_scan", {"n_points": 5, "n_bar": 0.0}), event_loop)
        assert resp["ok"] is True
        result = resp["result"]
        assert "t_us"      in result
        assert "p_excited" in result
        assert "t_pi_us"   in result
        assert len(result["t_us"]) == 5

    def test_rabi_scan_p_e_range(self, server, event_loop):
        """All P_e values must be in [0, 1]."""
        resp = _run(send_request("rabi_scan", {"n_points": 10}), event_loop)
        for p in resp["result"]["p_excited"]:
            assert -0.01 <= p <= 1.01, f"P_e out of range: {p}"

    def test_sideband_cooling(self, server, event_loop):
        """sideband_cooling returns n̄_final < n̄_0."""
        resp = _run(
            send_request("sideband_cooling", {"n_bar_0": 10.0, "n_cycles": 100}),
            event_loop,
        )
        assert resp["ok"] is True
        r = resp["result"]
        assert r["n_bar_final"] < r["n_bar_initial"]

    def test_readout_command(self, server, event_loop):
        """readout command returns mean_counts, threshold, fidelity."""
        resp = _run(
            send_request("readout", {"state": 0, "n_shots": 50}),
            event_loop,
        )
        assert resp["ok"] is True
        r = resp["result"]
        assert "mean_counts" in r
        assert "threshold"   in r
        assert "fidelity"    in r
        assert 0.0 <= r["fidelity"] <= 1.0

    def test_ms_gate_command(self, server, event_loop):
        """ms_gate command returns analytic fidelity."""
        resp = _run(
            send_request("ms_gate", {"eta": 0.1, "n_bar": 0.0}),
            event_loop,
        )
        assert resp["ok"] is True
        F = resp["result"]["fidelity"]
        assert abs(F - 0.99) < 1e-5

    def test_unknown_command_returns_error(self, server, event_loop):
        """Unknown command must return ok=False with an error message."""
        resp = _run(send_request("bogus_cmd", {}), event_loop)
        assert resp["ok"] is False
        assert "error" in resp
        assert "bogus_cmd" in resp["error"]

    def test_multiple_requests_on_same_connection(self, server, event_loop):
        """
        The server must handle two sequential requests on a single connection.
        We test this by opening a raw connection and sending two JSON lines.
        """
        async def multi_req():
            reader, writer = await asyncio.open_connection(HOST, PORT)
            for cmd in ["sideband_cooling", "ms_gate"]:
                line = json.dumps({"cmd": cmd, "params": {}}) + "\n"
                writer.write(line.encode())
                await writer.drain()
                resp_line = await reader.readline()
                resp = json.loads(resp_line.decode())
                assert resp["ok"] is True, f"cmd {cmd} failed: {resp}"
            writer.close()
            await writer.wait_closed()

        _run(multi_req(), event_loop)
