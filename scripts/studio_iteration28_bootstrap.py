from pathlib import Path
import shutil

capture = Path('apps/studio/visual-preview')
baselines = Path('apps/studio/visual-baselines')
files = [
    '01-create-image-centered.png',
    '02b-image-picker-keyboard-focus.png',
    '05b-video-output-controls.png',
    '05f-video-picker-keyboard-focus.png',
    '05i-video-audio-on.png',
    '09-mobile-create.png',
    '10-gallery-grid.png',
    '10b-gallery-keyboard-focus.png',
    '14-gallery-mobile-manager.png',
]
baselines.mkdir(parents=True, exist_ok=True)
for name in files:
    source = capture / name
    if not source.exists():
        raise SystemExit(f'missing capture {source}')
    shutil.copy2(source, baselines / name)
print(f'Bootstrapped {len(files)} reviewed baseline surfaces.')
