from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / "docs/studio-ui-polish-iteration-brief.md"
text = path.read_text()
old = "Remaining high-value work includes shared Image/Video aspect-picker architecture, consistent resolution terminology, stronger Generate/audio affordances, richer real lifecycle feedback, bulk-management improvements, Create composition refactoring, Gallery naming/internal cleanup, App.jsx responsibility reduction, card metadata simplification, search/sort, design-token consolidation, broader accessibility, and true screenshot-baseline regression testing."
new = "Remaining high-value work includes consistent resolution terminology and delivery dimensions, stronger Generate/audio affordances, richer real lifecycle feedback, bulk-management improvements, Create composition refactoring, Gallery naming/internal cleanup, App.jsx responsibility reduction, card metadata simplification, search/sort, design-token consolidation, broader accessibility, and true screenshot-baseline regression testing."
if text.count(old) != 1:
    raise RuntimeError(f"Expected one stale baseline sentence, found {text.count(old)}")
path.write_text(text.replace(old, new, 1))
print("Iteration 8 handoff baseline made consistent")
