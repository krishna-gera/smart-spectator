#!/usr/bin/env python3
"""
Smart Spectator - First-Run System Doctor & Diagnostic Verification
Conforms to Section 24 of Phase 8 Master Specification.
Audits runtime environment, dependencies, storage paths, ports, model artifacts,
database schema, and network interfaces.
Outputs structured PASS / WARN / FAIL statuses with actionable recommendations.
"""

import sys
import os
import socket
import json
import platform
import shutil
from pathlib import Path
from typing import Tuple, List, Dict, Any

# Ensure repository root is in sys.path
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))


class SystemDoctor:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def log_check(self, category: str, item: str, status: str, message: str, advice: str = ""):
        self.results.append({
            "category": category,
            "item": item,
            "status": status,
            "message": message,
            "advice": advice,
        })
        color = "\033[92m" if status == "PASS" else ("\033[93m" if status == "WARN" else "\033[91m")
        reset = "\033[0m"
        print(f"[{color}{status:4}{reset}] {category:<14} | {item:<22} : {message}")
        if advice and status != "PASS":
            print(f"       -> Action: {advice}")

    def check_python(self):
        v = sys.version_info
        ver_str = f"{v.major}.{v.minor}.{v.micro}"
        if v.major == 3 and v.minor >= 10:
            self.log_check("Environment", "Python Version", "PASS", f"Python {ver_str} installed")
        else:
            self.log_check(
                "Environment", "Python Version", "FAIL",
                f"Python {ver_str} found (requires >= 3.10)",
                "Install Python 3.10 or 3.11"
            )

    def check_dependencies(self):
        required = ["fastapi", "uvicorn", "pydantic", "sqlite3", "numpy", "PIL", "onnxruntime", "psutil"]
        missing = []
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        if not missing:
            self.log_check("Dependencies", "Core Packages", "PASS", "All required Python libraries available")
        else:
            self.log_check(
                "Dependencies", "Core Packages", "FAIL",
                f"Missing packages: {', '.join(missing)}",
                f"Run: pip install -r requirements.txt"
            )

    def check_directories(self):
        dirs = ["recordings", "snapshots", "logs", "backups", "data", "ai/models/releases"]
        all_ok = True
        for d in dirs:
            p = root_path / d
            if not p.exists():
                all_ok = False
                p.mkdir(parents=True, exist_ok=True)
        if all_ok:
            self.log_check("Storage", "Directory Structure", "PASS", "All required runtime directories present")
        else:
            self.log_check("Storage", "Directory Structure", "WARN", "Created missing required runtime directories")

    def check_disk_space(self):
        try:
            total, used, free = shutil.disk_usage(root_path)
            free_mb = round(free / (1024 * 1024), 1)
            if free_mb >= 500:
                self.log_check("Storage", "Free Disk Space", "PASS", f"{free_mb} MB available (threshold 500 MB)")
            else:
                self.log_check(
                    "Storage", "Free Disk Space", "WARN",
                    f"Only {free_mb} MB available (below 500 MB threshold)",
                    "Free disk space to allow event MP4 clip recording"
                )
        except Exception as e:
            self.log_check("Storage", "Free Disk Space", "WARN", f"Could not determine disk usage: {e}")

    def check_ports(self):
        for port, label in [(8000, "REST / Web Hub"), (8554, "TCP Media Ingestion")]:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                res = s.connect_ex(("127.0.0.1", port))
                if res == 0:
                    self.log_check("Networking", f"Port {port} ({label})", "WARN", f"Port {port} is currently bound/in use")
                else:
                    self.log_check("Networking", f"Port {port} ({label})", "PASS", f"Port {port} is free and ready to bind")

    def check_network_interface(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            self.log_check("Networking", "Local LAN IP", "PASS", f"Active LAN address: {ip}")
        except Exception:
            self.log_check("Networking", "Local LAN IP", "WARN", "Could not detect active local IP; fallback 127.0.0.1")

    def check_database(self):
        try:
            from services.hub_backend.database.connection import init_database, get_db_connection
            from services.hub_backend.database.migrations import MigrationTracker
            init_database()
            with get_db_connection() as conn:
                tracker = MigrationTracker(conn)
                cur_ver = tracker.get_current_version()
            self.log_check("Database", "SQLite Schema", "PASS", f"Database initialized (Schema version: {cur_ver})")
        except Exception as e:
            self.log_check("Database", "SQLite Schema", "FAIL", f"Database check failed: {e}", "Verify write permissions")

    def check_models(self):
        try:
            from ai.models.validator import model_validator
            rep = model_validator.validate_all()
            if rep["status"] == "READY":
                self.log_check("AI Models", "Model Checksums", "PASS", "All release models verified against manifest.json")
            else:
                self.log_check("AI Models", "Model Checksums", "WARN", f"Status: {rep['status']}: {rep.get('error')}")
        except Exception as e:
            self.log_check("AI Models", "Model Checksums", "FAIL", f"Validation exception: {e}")

    def check_ai_provider(self):
        try:
            from ai.inference.manager import provider_manager
            backends = provider_manager.detect_available_backends()
            backend, prov = provider_manager.get_preferred_provider("auto")
            names = [b.value for b in backends]
            self.log_check("Inference", "Execution Providers", "PASS", f"Detected: {names} | Active: {prov.provider_name}")
        except Exception as e:
            self.log_check("Inference", "Execution Providers", "FAIL", f"Provider detection failed: {e}")

    def check_client_ui(self):
        client_index = root_path / "apps" / "client" / "index.html"
        if client_index.exists():
            self.log_check("Client UI", "Dashboard Assets", "PASS", "Monitoring Client web app present")
        else:
            self.log_check("Client UI", "Dashboard Assets", "WARN", f"Client index missing at {client_index}")

    def run_all(self) -> bool:
        print("=" * 70)
        print(" Smart Spectator — System Diagnostic Doctor (First-Run Verification)")
        print("=" * 70)

        self.check_python()
        self.check_dependencies()
        self.check_directories()
        self.check_disk_space()
        self.check_ports()
        self.check_network_interface()
        self.check_database()
        self.check_models()
        self.check_ai_provider()
        self.check_client_ui()

        fails = [r for r in self.results if r["status"] == "FAIL"]
        warns = [r for r in self.results if r["status"] == "WARN"]
        passes = [r for r in self.results if r["status"] == "PASS"]

        print("=" * 70)
        print(f"Summary: \033[92m{len(passes)} PASS\033[0m | \033[93m{len(warns)} WARN\033[0m | \033[91m{len(fails)} FAIL\033[0m")
        if fails:
            print("\nResult: System has blocking issues that require remediation.")
            return False
        elif warns:
            print("\nResult: System is functional with minor operational warnings.")
            return True
        else:
            print("\nResult: System is 100% HEALTHY and ready for operation!")
            return True


if __name__ == "__main__":
    doc = SystemDoctor()
    success = doc.run_all()
    sys.exit(0 if success else 1)
