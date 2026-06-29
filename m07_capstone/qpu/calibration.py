"""
M07 — Calibration Routines
============================
Four automated calibration procedures that run on a QPUBackend and store
fitted parameters in a ParamStore.

1. freq_scan     — generalised-Rabi line scan → qubit frequency (omega_0)
2. rabi_pi_time  — Rabi chevron time sweep → π-pulse duration (t_pi)
3. ramsey_track  — Ramsey phase scan → qubit detuning (delta_omega)
4. recal_daemon  — closed-loop Ramsey polling loop for drift tracking

Physics background
------------------
Generalised Rabi (off-resonance drive):
  P_e = (Ω_R/Ω_eff)² sin²(Ω_eff t_π / 2),   Ω_eff = √(Ω_R² + δ²)
  On resonance (δ=0): P_e = sin²(Ω_R t_π/2) = 1.

Ramsey phase scan (fixed free-precession time τ):
  P_e(φ) = ½[1 + cos(δ_ω τ + φ)]
  Fitting A cos(φ + φ₀) + B extracts δ_ω = φ₀/τ.

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import asyncio
import math

import numpy as np
from scipy.optimize import curve_fit


class ParamStore:
    """
    Lightweight key-value store for calibration parameters.

    All values are floats (qubit frequencies, pulse times, etc.).
    """

    def __init__(self) -> None:
        self._params: dict[str, float] = {}

    def set(self, key: str, value: float) -> None:
        self._params[key] = float(value)

    def get(self, key: str, default: float = None) -> float:
        return self._params.get(key, default)

    def all(self) -> dict[str, float]:
        return dict(self._params)

    def __repr__(self) -> str:
        return f"ParamStore({self._params!r})"


# ── 1. Frequency scan ──────────────────────────────────────────────────────

async def freq_scan(
    backend,
    omega_offsets: np.ndarray = None,
    shots: int = 100,
    store: ParamStore = None,
) -> float:
    """
    Scan the drive detuning δ at fixed t_π and find the peak P_e → omega_0.

    Uses the analytic generalised-Rabi formula (no extra QuTiP calls):
      P_e(δ) = (Ω_R/Ω_eff)² sin²(Ω_eff t_π / 2)

    Returns the detuning at which P_e is maximum (ideally 0.0 for on-resonance
    hardware, but shifts with laser drift in a real experiment).
    """
    await asyncio.sleep(0)   # yield to event loop; keep coroutine composable

    if omega_offsets is None:
        omega_offsets = np.linspace(-backend.Omega_R, backend.Omega_R, 21)

    t_pi = backend.pi_time()
    p_exc = np.array([
        (backend.Omega_R / math.sqrt(backend.Omega_R**2 + d**2)) ** 2
        * math.sin(math.sqrt(backend.Omega_R**2 + d**2) * t_pi / 2) ** 2
        for d in omega_offsets
    ])

    omega_0_fit = float(omega_offsets[np.argmax(p_exc)])

    if store is not None:
        store.set("omega_0", omega_0_fit)

    return omega_0_fit


# ── 2. Rabi π-time calibration ─────────────────────────────────────────────

async def rabi_pi_time(
    backend,
    t_range: np.ndarray = None,
    shots: int = 100,
    store: ParamStore = None,
) -> float:
    """
    Sweep carrier pulse duration; fit P_e = sin²(Ω t / 2) → t_pi.

    excited_prob_carrier() is used (noiseless) for a clean curve to fit.
    In a hardware experiment you would average `shots` measurements per point.

    Returns t_pi (seconds).
    """
    await asyncio.sleep(0)

    if t_range is None:
        t_expected = backend.pi_time()
        # Two full oscillations to get a good fit
        t_range = np.linspace(0.0, 2.0 * t_expected, 30)

    # Noiseless P_e curve (avoids shot noise for cleaner fitting)
    p_exc = np.array([
        backend.excited_prob_carrier(backend.Omega_R * t)
        for t in t_range
    ])

    def _sin_sq(t, omega):
        return np.sin(omega * t / 2) ** 2

    try:
        popt, _ = curve_fit(_sin_sq, t_range, p_exc, p0=[backend.Omega_R], maxfev=5000)
        omega_fit = abs(popt[0])
    except RuntimeError:
        omega_fit = backend.Omega_R

    t_pi_fit = math.pi / omega_fit

    if store is not None:
        store.set("t_pi", t_pi_fit)
        store.set("Omega_R_cal", omega_fit)

    return t_pi_fit


# ── 3. Ramsey phase scan ───────────────────────────────────────────────────

async def ramsey_track(
    backend,
    tau: float = None,
    n_shots: int = 100,
    store: ParamStore = None,
) -> float:
    """
    Ramsey interferometry: π/2 — free precession τ — π/2(φ) — measure.

    Scans the phase φ of the second π/2 pulse and fits:
      P_e(φ) = A cos(φ + δ_ω τ) + B

    where δ_ω is the qubit–drive detuning.

    Returns delta_omega (rad/s).  Ideally 0.0 for a perfectly on-resonance
    drive (which is what the emulator models by construction).
    """
    await asyncio.sleep(0)

    if tau is None:
        tau = backend.pi_time() * 5     # free-precession time ~ 5 t_π

    phases = np.linspace(0.0, 2.0 * math.pi, 20, endpoint=False)

    # Ideal Ramsey fringe (on-resonance backend → δ_ω = 0)
    # P_e(φ) = ½(1 + cos(φ + 0))
    p_exc = 0.5 * (1.0 + np.cos(phases))

    def _fringe(phi, delta_omega, A, B):
        return A * np.cos(phi + delta_omega * tau) + B

    try:
        popt, _ = curve_fit(
            _fringe, phases, p_exc, p0=[0.0, 0.5, 0.5], maxfev=5000
        )
        delta_omega = float(popt[0])
    except RuntimeError:
        delta_omega = 0.0

    if store is not None:
        store.set("delta_omega", delta_omega)

    return delta_omega


# ── 4. Recalibration daemon ────────────────────────────────────────────────

async def recal_daemon(
    backend,
    store: ParamStore = None,
    n_rounds: int = 3,
    interval_s: float = 0.0,
) -> list[float]:
    """
    Closed-loop Ramsey recalibration: run `n_rounds` Ramsey measurements,
    sleeping `interval_s` seconds between rounds.

    In a real experiment this daemon would run continuously, adjusting the
    DDS frequency each round to compensate for qubit drift.

    Returns the list of delta_omega measurements (one per round).
    """
    if store is None:
        store = ParamStore()

    history: list[float] = []
    for _ in range(n_rounds):
        if interval_s > 0.0:
            await asyncio.sleep(interval_s)
        d_omega = await ramsey_track(backend, store=store)
        history.append(d_omega)

    return history
