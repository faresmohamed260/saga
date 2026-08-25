# Create advanced presets

Studio's Create Advanced settings must describe controls that are actually consumed by the active production workflow.

## FLUX.2 Klein 9B

- Model: `flux2-klein-9b`
- Workflow: `flux2-klein-image-edit`
- Default steps: **4**
- Default CFG: **1.0**
- Steps and CFG are forwarded to the FLUX worker and remain editable.

## REDGraft LTX 2.5 / Sulphur2

- Model: `ltx25-redgraft`
- Workflow: `ltx25-redgraft-video`
- Default CFG: **1.0**
- Sampling recipe: **11 total denoise transitions** — **8 base + 3 refine**

The current REDGraft/Sulphur2 worker loads its custom checkpoint directly and does not load a separate distillation LoRA. Its custom sigma schedules already encode the two-stage 8 + 3 recipe, so Studio exposes the total step count as a fixed value instead of presenting an arbitrary step slider. The API gateway and worker reject non-11 LTX step counts so the UI cannot imply unsupported sampling behavior.

Video Aspect and Frame rate are Advanced settings. Aspect can remain Auto and follow the attached reference; manual aspect and 24/25/30 fps are forwarded to the worker.

## Create output wall

Create does not ship stock face/scene placeholder generations. Newly generated session outputs are shown first and existing Favorites are used as the visual fallback while no new result occupies a slot.
