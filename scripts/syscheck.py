#!/usr/bin/env python3
"""
ANVESHAK — System Requirements Checker

Validates host system against minimum and recommended hardware requirements
for the Anveshak AI-OSINT platform. Pure stdlib — no external dependencies.

Usage:
    python scripts/syscheck.py

Exit codes:
    0 — Minimum requirements met
    1 — Minimum requirements NOT met

See hardware.md for upgrade paths and production tier details.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
from typing import NamedTuple

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

# Disable colours if redirected to a file/pipe
if not sys.stdout.isatty():
    RESET = BOLD = RED = GREEN = YELLOW = BLUE = CYAN = ""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_RAM_GB = 16
REC_RAM_GB = 32
MIN_DISK_GB = 20
REC_DISK_GB = 100
MIN_DOCKER_MAJOR = 20

PORTS = [3000, 3001, 5433, 6379, 8000, 8001, 8002, 8003, 8005, 8006, 8007, 9090, 9121, 9187, 11434]

# Production tiers from hardware.md
TIERS = [
    (
        "CPU-only (dev/testing)",
        "16-core, 32GB RAM, 512GB NVMe",
        "~₹80K",
        "~50 articles/day, 5min/report",
    ),
    (
        "Demo/eval (recommended)",
        "RTX 3080, 32GB RAM, 1TB NVMe",
        "~₹1.5–2L",
        "~2K articles/day, 30s/report",
    ),
    ("IAF production", "RTX 4090, 64GB RAM, 2TB NVMe", "~₹3–4L", "~10K articles/day, 10s/report"),
]


class CheckResult(NamedTuple):
    name: str
    current: str
    minimum: str
    min_ok: bool
    recommended: str
    rec_ok: bool


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 10) -> str | None:
    """Run a command and return stdout, or None on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def detect_ram_gb() -> float:
    """Return total RAM in GB."""
    system = platform.system()
    if system == "Darwin":
        out = _run(["sysctl", "-n", "hw.memsize"])
        if out:
            return int(out) / (1024**3)
    elif system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024**2)
        except OSError:
            pass
    return 0.0


def detect_ram_available_gb() -> float:
    """Return available RAM in GB."""
    system = platform.system()
    if system == "Darwin":
        out = _run(["vm_stat"])
        if out:
            page_size = 16384  # Apple Silicon default
            ps_out = _run(["sysctl", "-n", "hw.pagesize"])
            if ps_out:
                page_size = int(ps_out)
            free_pages = 0
            for line in out.splitlines():
                if "Pages free:" in line:
                    free_pages += int(line.split(":")[1].strip().rstrip("."))
                elif "Pages inactive:" in line:
                    free_pages += int(line.split(":")[1].strip().rstrip("."))
                elif "Pages purgeable:" in line:
                    free_pages += int(line.split(":")[1].strip().rstrip("."))
            return (free_pages * page_size) / (1024**3)
    elif system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        kb = int(line.split()[1])
                        return kb / (1024**2)
        except OSError:
            pass
    return 0.0


def detect_cpu_cores() -> int:
    """Return number of CPU cores."""
    try:
        return os.cpu_count() or 0
    except Exception:
        return 0


def detect_disk_free_gb() -> float:
    """Return free disk space in GB for the working directory."""
    try:
        usage = shutil.disk_usage(os.getcwd())
        return usage.free / (1024**3)
    except OSError:
        return 0.0


def detect_disk_total_gb() -> float:
    """Return total disk space in GB."""
    try:
        usage = shutil.disk_usage(os.getcwd())
        return usage.total / (1024**3)
    except OSError:
        return 0.0


def detect_docker_version() -> str | None:
    """Return Docker version string or None."""
    out = _run(["docker", "version", "--format", "{{.Server.Version}}"])
    if not out:
        out = _run(["docker", "--version"])
        if out and "version" in out.lower():
            # "Docker version 24.0.6, build ..."
            parts = out.split()
            for i, p in enumerate(parts):
                if p.lower() == "version":
                    return parts[i + 1].rstrip(",") if i + 1 < len(parts) else None
    return out


def docker_major_version(version_str: str | None) -> int:
    """Extract major version number from Docker version string."""
    if not version_str:
        return 0
    try:
        return int(version_str.split(".")[0])
    except (ValueError, IndexError):
        return 0


def detect_docker_running() -> bool:
    """Check if Docker daemon is running."""
    out = _run(["docker", "info"])
    return out is not None


def detect_compose_version() -> str | None:
    """Return Docker Compose version or None."""
    out = _run(["docker", "compose", "version", "--short"])
    if out:
        return out
    out = _run(["docker-compose", "version", "--short"])
    return out


def detect_gpu() -> tuple[str, str]:
    """
    Detect GPU. Returns (gpu_name, tier).
    tier is one of: 'none', 'basic', 'demo', 'production'
    """
    system = platform.system()

    if system == "Darwin":
        out = _run(["system_profiler", "SPDisplaysDataType"])
        if out:
            for line in out.splitlines():
                stripped = line.strip()
                if "Chipset Model:" in stripped or "Chip:" in stripped:
                    name = stripped.split(":", 1)[1].strip()
                    if "Apple" in name:
                        return f"{name} (Metal)", "basic"
                    return name, "basic"
                if "Metal" in stripped and "Supported" in stripped:
                    return "Metal GPU (unknown)", "basic"
        # Check Apple Silicon
        cpu_brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if cpu_brand and "Apple" in cpu_brand:
            return f"{cpu_brand} (Metal)", "basic"
        return "None detected", "none"

    elif system == "Linux":
        out = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
        if out:
            gpu_name = out.splitlines()[0].strip()
            name_upper = gpu_name.upper()
            if any(x in name_upper for x in ["4090", "A100", "H100", "A6000", "L40", "A40"]):
                return gpu_name, "production"
            elif any(x in name_upper for x in ["3080", "3090", "4070", "4080", "A5000", "A4000"]):
                return gpu_name, "demo"
            else:
                return gpu_name, "basic"

    return "None detected", "none"


def check_port(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    """Return True if port is available (not in use), False if occupied."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            return result != 0  # 0 means connected = port in use
    except OSError:
        return True  # Cannot connect = port is available


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------


def _pad(text: str, width: int) -> str:
    """Pad text to width, accounting for ANSI escape sequences."""
    # Strip ANSI to calculate visible length
    import re

    visible = re.sub(r"\033\[[0-9;]*m", "", text)
    padding = width - len(visible)
    if padding > 0:
        return text + " " * padding
    return text


def _status(ok: bool) -> str:
    if ok:
        return f"{GREEN}✓{RESET}"
    return f"{RED}✗{RESET}"


def print_table(results: list[CheckResult]) -> None:
    """Print the results as an ASCII table with ANSI colours."""
    # Column widths (visible characters)
    c0 = 20  # Check
    c1 = 16  # Current
    c2 = 14  # Minimum
    c3 = 20  # Recommended

    total = c0 + c1 + c2 + c3 + 5  # 5 = separators

    # Top border
    print(f"{BLUE}╔{'═' * (total)}╗{RESET}")
    title = "ANVESHAK — System Requirements Check"
    pad_l = (total - len(title)) // 2
    pad_r = total - len(title) - pad_l
    print(f"{BLUE}║{RESET}{BOLD}{CYAN}{' ' * pad_l}{title}{' ' * pad_r}{RESET}{BLUE}║{RESET}")

    # Header separator
    print(f"{BLUE}╠{'═' * c0}╦{'═' * c1}╦{'═' * c2}╦{'═' * c3}╣{RESET}")

    # Header row
    print(
        f"{BLUE}║{RESET}{BOLD}"
        f" {_pad('Check', c0 - 1)}"
        f"{BLUE}║{RESET}{BOLD}"
        f" {_pad('Current', c1 - 1)}"
        f"{BLUE}║{RESET}{BOLD}"
        f" {_pad('Minimum', c2 - 1)}"
        f"{BLUE}║{RESET}{BOLD}"
        f" {_pad('Recommended', c3 - 1)}"
        f"{BLUE}║{RESET}"
    )

    # Header-body separator
    print(f"{BLUE}╠{'═' * c0}╬{'═' * c1}╬{'═' * c2}╬{'═' * c3}╣{RESET}")

    # Data rows
    for r in results:
        min_col = f"{r.minimum} {_status(r.min_ok)}" if r.minimum else "—"
        rec_col = f"{r.recommended} {_status(r.rec_ok)}" if r.recommended else "—"

        print(
            f"{BLUE}║{RESET}"
            f" {_pad(r.name, c0 - 1)}"
            f"{BLUE}║{RESET}"
            f" {_pad(r.current, c1 - 1)}"
            f"{BLUE}║{RESET}"
            f" {_pad(min_col, c2 - 1)}"
            f"{BLUE}║{RESET}"
            f" {_pad(rec_col, c3 - 1)}"
            f"{BLUE}║{RESET}"
        )

    # Bottom border
    print(f"{BLUE}╚{'═' * c0}╩{'═' * c1}╩{'═' * c2}╩{'═' * c3}╝{RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    results: list[CheckResult] = []
    all_min_ok = True

    # --- RAM ---
    total_ram = detect_ram_gb()
    avail_ram = detect_ram_available_gb()
    ram_min_ok = total_ram >= MIN_RAM_GB
    ram_rec_ok = total_ram >= REC_RAM_GB
    if not ram_min_ok:
        all_min_ok = False
    results.append(
        CheckResult(
            "RAM (total)",
            f"{total_ram:.0f} GB",
            f"{MIN_RAM_GB} GB",
            ram_min_ok,
            f"{REC_RAM_GB} GB",
            ram_rec_ok,
        )
    )
    results.append(
        CheckResult(
            "RAM (available)",
            f"{avail_ram:.1f} GB",
            "6 GB",
            avail_ram >= 6.0,
            "16 GB",
            avail_ram >= 16.0,
        )
    )
    if avail_ram < 6.0:
        all_min_ok = False

    # --- CPU ---
    cores = detect_cpu_cores()
    results.append(
        CheckResult(
            "CPU cores",
            str(cores),
            "4",
            cores >= 4,
            "16",
            cores >= 16,
        )
    )
    if cores < 4:
        all_min_ok = False

    # --- Disk ---
    disk_free = detect_disk_free_gb()
    disk_total = detect_disk_total_gb()
    disk_min_ok = disk_free >= MIN_DISK_GB
    disk_rec_ok = disk_free >= REC_DISK_GB
    if not disk_min_ok:
        all_min_ok = False
    results.append(
        CheckResult(
            "Disk free",
            f"{disk_free:.0f} GB / {disk_total:.0f} GB",
            f"{MIN_DISK_GB} GB",
            disk_min_ok,
            f"{REC_DISK_GB} GB",
            disk_rec_ok,
        )
    )

    # --- Docker ---
    docker_ver = detect_docker_version()
    docker_running = detect_docker_running()
    docker_ok = docker_ver is not None and docker_major_version(docker_ver) >= MIN_DOCKER_MAJOR
    if not docker_ok:
        all_min_ok = False
    results.append(
        CheckResult(
            "Docker",
            docker_ver or "NOT FOUND",
            f"v{MIN_DOCKER_MAJOR}+",
            docker_ok,
            "",
            docker_ok,
        )
    )
    results.append(
        CheckResult(
            "Docker daemon",
            f"{GREEN}running{RESET}" if docker_running else f"{RED}stopped{RESET}",
            "running",
            docker_running,
            "",
            docker_running,
        )
    )
    if not docker_running:
        all_min_ok = False

    # --- Docker Compose ---
    compose_ver = detect_compose_version()
    results.append(
        CheckResult(
            "Docker Compose",
            compose_ver or "NOT FOUND",
            "v2+",
            compose_ver is not None,
            "",
            compose_ver is not None,
        )
    )
    if compose_ver is None:
        all_min_ok = False

    # --- GPU ---
    gpu_name, gpu_tier = detect_gpu()
    tier_labels = {
        "none": f"{YELLOW}None{RESET}",
        "basic": f"{CYAN}Basic (Metal/iGPU){RESET}",
        "demo": f"{GREEN}Demo-tier{RESET}",
        "production": f"{GREEN}{BOLD}Production-tier{RESET}",
    }
    results.append(
        CheckResult(
            "GPU",
            gpu_name,
            "optional",
            True,  # GPU is not required for minimum
            "RTX 3080+",
            gpu_tier in ("demo", "production"),
        )
    )

    # --- Ports ---
    busy_ports = []
    free_ports = []
    for port in PORTS:
        if check_port(port):
            free_ports.append(port)
        else:
            busy_ports.append(port)

    ports_ok = len(busy_ports) == 0
    if busy_ports:
        port_current = f"{RED}{len(busy_ports)} in use{RESET}"
    else:
        port_current = f"{GREEN}all free{RESET}"

    results.append(
        CheckResult(
            "Ports",
            port_current,
            "all free",
            ports_ok,
            "",
            ports_ok,
        )
    )

    # --- Platform ---
    system = platform.system()
    machine = platform.machine()
    results.append(
        CheckResult(
            "Platform",
            f"{system} {machine}",
            "macOS/Linux",
            system in ("Darwin", "Linux"),
            "",
            system in ("Darwin", "Linux"),
        )
    )

    # -----------------------------------------------------------------------
    # Print table
    # -----------------------------------------------------------------------
    print()
    print_table(results)

    # -----------------------------------------------------------------------
    # Port details (if any busy)
    # -----------------------------------------------------------------------
    if busy_ports:
        print()
        print(f"  {YELLOW}Ports in use:{RESET} {', '.join(str(p) for p in busy_ports)}")
        print(f"  {CYAN}Stop conflicting services before running `make up`.{RESET}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    if all_min_ok:
        print(f"  {GREEN}{BOLD}✓ MINIMUM REQUIREMENTS MET{RESET}")
    else:
        print(f"  {RED}{BOLD}✗ MINIMUM REQUIREMENTS NOT MET{RESET}")

    # GPU summary
    if gpu_tier != "none":
        print(f"  {GREEN}GPU detected{RESET} — {tier_labels[gpu_tier]}")
    else:
        print(f"  {YELLOW}No GPU detected{RESET} — CPU-only mode (adequate for dev/testing)")

    # Hardware tier classification
    print()
    print(f"  {BOLD}Hardware tier classification:{RESET}")
    if gpu_tier == "production":
        print(
            f"    {GREEN}{BOLD}▸ IAF Production{RESET}"
            f" — ~10K articles/day, 10s/report, 72b LLM capable"
        )
    elif gpu_tier == "demo":
        print(f"    {GREEN}▸ Demo/Eval{RESET} — ~2K articles/day, 30s/report")
    else:
        print(f"    {CYAN}▸ CPU-only{RESET} — ~50 articles/day, 5min/report")

    # Tier table
    print()
    print(f"  {BOLD}Production tiers (from hardware.md):{RESET}")
    print(f"  {'Tier':<28} {'Hardware':<38} {'Cost':<10} {'Throughput'}")
    print(f"  {'─' * 28} {'─' * 38} {'─' * 10} {'─' * 36}")
    for tier_name, hw, cost, throughput in TIERS:
        print(f"  {tier_name:<28} {hw:<38} {cost:<10} {throughput}")

    print()
    print(f"  {CYAN}See hardware.md for upgrade paths and env var configuration.{RESET}")
    print()

    return 0 if all_min_ok else 1


if __name__ == "__main__":
    sys.exit(main())
