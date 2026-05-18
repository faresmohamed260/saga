from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
CONFIG = json.loads((MODULE_DIR / "gateway_config.json").read_text(encoding="utf-8"))
PYTHON_EXE = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
RUN_GATEWAY = MODULE_DIR / "run_gateway.py"


class ModalComfyUIGatewayService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ModalComfyUIGateway"
    _svc_display_name_ = "Modal ComfyUI Gateway"
    _svc_description_ = "Local reverse proxy and status dashboard for Modal-backed ComfyUI."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process: subprocess.Popen[str] | None = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=30)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Starting Modal ComfyUI Gateway service")
        self.process = subprocess.Popen(
            [str(PYTHON_EXE), str(RUN_GATEWAY)],
            cwd=str(PROJECT_ROOT),
        )
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(ModalComfyUIGatewayService)
