from pathlib import Path

p = Path('integrations/comfyui/ltx23_app.py')
s = p.read_text(encoding='utf-8')

def one(old, new):
    global s
    if s.count(old) != 1:
        raise SystemExit(f'expected one match: {old[:80]!r}')
    s = s.replace(old, new, 1)

one('GPU_TYPE = os.environ.get("MODAL_LTX25_GPU", "A10")\n', 'GPU_CHOICES = [x.strip() for x in os.environ.get("MODAL_LTX25_GPU", "L40S,A100-40GB").split(",") if x.strip()]\nGPU_REQUEST: str | list[str] = GPU_CHOICES[0] if len(GPU_CHOICES) == 1 else GPU_CHOICES\nGPU_LABEL = ",".join(GPU_CHOICES)\n')
one('    gpu=GPU_TYPE,\n', '    gpu=GPU_REQUEST,\n')
one('            "gpu": GPU_TYPE,\n', '            "gpu": GPU_LABEL,\n')
one('            raise ValueError(f"{resolution} is not enabled for the REDGraft LTX 2.5 A10 runtime")\n', '            raise ValueError(f"{resolution} is not enabled for the REDGraft LTX 2.5 runtime")\n')
one('''        self.process = subprocess.Popen(\n            [\n                "python",\n                "main.py",\n                "--listen",\n                "127.0.0.1",\n                "--port",\n                "8188",\n                "--lowvram",\n                "--reserve-vram",\n                "2",\n                "--disable-auto-launch",\n                "--preview-method",\n                "none",\n            ],\n            cwd=COMFY_DIR,\n        )\n''', '''        launch_command = [\n            "python", "main.py", "--listen", "127.0.0.1", "--port", "8188",\n            "--reserve-vram", "2", "--disable-auto-launch", "--preview-method", "none",\n        ]\n        if any(choice.upper() == "A10" for choice in GPU_CHOICES):\n            launch_command.append("--lowvram")\n        self.process = subprocess.Popen(launch_command, cwd=COMFY_DIR)\n''')
p.write_text(s, encoding='utf-8')
