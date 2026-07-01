# M08 — qprep dev/CI container image.
#
# WHY no Vivado/xsim: Vivado is a multi-GB proprietary install gated by an
# Xilinx license file tied to this workstation. It can't be pulled into a
# public image or a GitHub Actions runner. This image (and CI) therefore
# only cover the open-source half of the toolchain: iverilog + Verilator +
# the Python/cocotb/QuTiP stack. M01 (SVA) and M09 (UVM) stay
# workstation-only with xsim; every other module builds/tests identically
# here, in CI, and on bare metal because they all read the same
# environment.yml.
FROM condaforge/miniforge3:24.9.2-0

WORKDIR /workspace

# Copy just the env spec first so `mamba env create` layer-caches across
# rebuilds that only touch source files below.
COPY environment.yml .
RUN mamba env create -f environment.yml && mamba clean -afy

# `docker run` doesn't source a login shell, so `conda activate` won't stick
# across RUN/CMD layers — `mamba run -n qprep` is the non-interactive
# equivalent and is what both the SHELL and ENTRYPOINT below use.
SHELL ["mamba", "run", "--no-capture-output", "-n", "qprep", "/bin/bash", "-c"]

COPY . .

ENTRYPOINT ["mamba", "run", "--no-capture-output", "-n", "qprep"]
CMD ["/bin/bash"]
