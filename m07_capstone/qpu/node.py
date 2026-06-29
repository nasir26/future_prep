"""
M07 — QPUNode: Two-Node Distributed Entanglement
=================================================
Models a physical QPU node that can:
  - Run local gate operations on its own ions (via QPUBackend).
  - Attempt heralded remote entanglement with a peer node via a photonic link.

Photonic link model
-------------------
In real ion-trap networks (e.g., Oxford / Innsbruck experiments):

  1. Each ion emits a photon entangled with its electronic state:
       |ion⟩ → (|↓⟩|V⟩ + |↑⟩|H⟩) / √2
  2. Photons from both nodes travel to a central beamsplitter (BSM).
  3. A two-photon coincidence at the BSM heralds entanglement.
  4. Per-photon collection + detection efficiency is η_link ≈ 0.3–0.7 (fibre).
  5. The heralding probability per attempt is p_herald = η_link² / 2.

Heralded Bell state
-------------------
A successful herald projects the ion pair into |Ψ-⟩ = (|↓↑⟩ − |↑↓⟩)/√2,
giving P("01") = P("10") = 0.5 and P("00") = P("11") = 0.

Author: Nasir Ali, C-DAC Noida
"""

from __future__ import annotations

import asyncio
import math

import numpy as np

from .backend import QPUBackend


class QPUNode:
    """
    A named QPU node with a local QPUBackend and an optional photonic link
    to a peer node.

    Parameters
    ----------
    node_id  : str         — human-readable node identifier
    backend  : QPUBackend  — local physics emulator (created if None)
    eta_link : float       — per-photon link efficiency (0 < η ≤ 1)
    rng      : Generator   — RNG for entanglement attempts
    """

    def __init__(
        self,
        node_id: str,
        backend: QPUBackend = None,
        eta_link: float = 0.5,
        rng: np.random.Generator = None,
    ) -> None:
        self.node_id = node_id
        self.backend = backend if backend is not None else QPUBackend()
        self.eta_link = eta_link
        self._rng = rng if rng is not None else np.random.default_rng(seed=hash(node_id) & 0xFFFF)
        self._peer: QPUNode | None = None

    # ── Connectivity ────────────────────────────────────────────────────────

    def connect(self, other: "QPUNode") -> None:
        """
        Establish a bidirectional photonic link between this node and `other`.

        In hardware this represents a fibre or free-space photonic channel.
        The link efficiency used for entanglement attempts is min(η_self, η_peer).
        """
        self._peer = other
        other._peer = self

    @property
    def peer(self) -> "QPUNode | None":
        return self._peer

    # ── Local operations ────────────────────────────────────────────────────

    async def run_local(
        self,
        theta: float,
        phi: float = 0.0,
        shots: int = 200,
    ) -> dict[str, int]:
        """
        Apply a carrier rotation (theta, phi) and measure locally.

        Returns {"0": n, "1": n}.
        """
        await asyncio.sleep(0)
        return self.backend.run_carrier(theta, phi, shots)

    # ── Distributed entanglement ────────────────────────────────────────────

    async def attempt_entanglement(
        self,
        n_heralded: int = 50,
    ) -> dict:
        """
        Simulate heralded remote entanglement with the connected peer.

        Loops until `n_heralded` successful Bell pairs are generated.

        Protocol per attempt
        --------------------
        1. Both nodes drive their ion → photon emission (entanglement with ion).
        2. Photons interfere at a BSM on the midpoint link.
        3. Two-photon coincidence (prob = η²/2) heralds a Bell pair.
        4. Successful pair is in |Ψ-⟩: 50% "01", 50% "10" on joint measurement.

        Parameters
        ----------
        n_heralded : int — number of heralded pairs to collect

        Returns
        -------
        dict with keys:
          "counts"   : {"01": int, "10": int} — joint measurement outcomes
          "attempts" : int — total entanglement attempts
          "successes": int — = n_heralded
          "herald_rate" : float — successes / attempts ≈ η² / 2
        """
        await asyncio.sleep(0)

        # Effective link efficiency: use this node's η (peer's η assumed equal)
        p_herald = self.eta_link ** 2 / 2.0

        counts = {"01": 0, "10": 0}
        attempts = 0

        for _ in range(n_heralded):
            while True:
                attempts += 1
                if self._rng.random() < p_herald:
                    # Heralded |Ψ-⟩ → "01" or "10" with equal probability
                    outcome = "01" if self._rng.integers(2) == 0 else "10"
                    counts[outcome] += 1
                    break

        herald_rate = n_heralded / attempts

        return {
            "counts": counts,
            "attempts": attempts,
            "successes": n_heralded,
            "herald_rate": herald_rate,
        }
