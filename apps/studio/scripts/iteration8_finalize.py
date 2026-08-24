from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:900]}")
    path.write_text(text.replace(old, new, 1))


def finalize_checklist() -> None:
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '''**Iteration 8 — shared Image/Video AspectPicker**\n\n- Status: `[~]` in progress\n- Working item: **08**\n- Rule: extract one reusable AspectPicker for Image and Video with shared ratio preview, option labels, keyboard behavior, responsive anchored positioning, and optional Auto/reference provenance; validate GitHub CI/visual previews and professional review before completion.\n''',
        '''**Iteration 8 — shared Image/Video AspectPicker**\n\n- Status: `[x]` complete\n- Completed item: **08**\n- Next item: **09 — standardize resolution terminology and expose actual delivery dimensions**\n- Rule: do not start Item 09 until the user explicitly says continue. Each future iteration must follow implement → deterministic test → GitHub CI/visual preview → inspect screenshots → professional critique → record improvements → update this file → stop for user approval.\n''',
    )
    replace_once(
        "docs/studio-ui-polish-checklist.md",
        '- [~] **08. Unify Image and Video aspect selection into one reusable `AspectPicker`.** Shared ratio preview, labels, selection behavior, keyboard support, responsive positioning, optional reference-source indicator. **Iteration 8 in progress.**\n',
        '- [x] **08. Unify Image and Video aspect selection into one reusable `AspectPicker`.** Image, Edit, and Video now use one shared `AspectPicker` and one canonical preset list, with a shared ratio preview, menu layout, keyboard behavior, responsive anchored positioning, and optional Auto/reference provenance. **Iteration 8 complete.**\n',
    )
    path = ROOT / "docs/studio-ui-polish-checklist.md"
    text = path.read_text().rstrip()
    log = '''

### Iteration 8 — shared Image/Video AspectPicker

- [x] Added `apps/studio/src/features/create/AspectPicker.jsx` as the single reusable aspect-selection component and canonical `ASPECT_PRESETS` source.
- [x] Image/Create and Edit now consume the shared picker instead of the prior local Image-specific `AspectPicker`; Video also consumes it instead of the generic Video `CompactPicker` path.
- [x] Shared behavior includes the ratio-shape preview panel, common labels, radio-menu semantics, Arrow/Home/End navigation, Enter/Space selection, Escape dismissal/focus return, outside-focus dismissal, and viewport-aware fixed positioning.
- [x] Video configures optional Auto behavior through the shared component, including effective ratio and explicit `From reference` provenance; Image uses the same picker without an Auto row and Edit supplies its reference-derived Auto state.
- [x] Deterministic Create and Video visual tests now assert that both modes render the same `data-shared-aspect-picker` trigger and shared aspect surface; existing picker focus, no-scroll, selection, Auto/manual, reference, and mobile-containment contracts remain enforced.
- [x] The first remote implementation run (`32675725844`) exposed a real focus-handoff problem when the newly mounted shared menu tried to move focus from its trigger. The implementation was refined rather than weakening the keyboard test.
- [x] A later refinement run (`32675995131`) advanced through focus handling and exposed a 2px menu overflow (`scrollHeight=366`, `clientHeight=364`). The menu sizing was corrected to include its border-box height; the no-scroll assertion was retained unchanged.
- [x] Successful shared-component validation run `32676138933` passed the poster/deferred-preview contract, build, and full visual suite; artifact `9502718139` confirmed Image/Video shared layout, keyboard focus, Auto/reference behavior, mobile containment, and Gallery regression coverage.
- [x] Professional visual review then found one remaining Item 08 issue: the default Video Auto provenance copy was truncated in the shared menu. The copy/layout was refined so `16:9 · Follows reference` remains fully legible while reference-derived states retain `From reference`.
- [x] Final standard Studio Visual Preview run `32676390654` passed on reviewed product head `333e32236b116be9a48234abada56582cbfd6ff2`; artifact `9502799506` was inspected across Image, Video, Edit, mobile Create, and Gallery with no remaining Item 08 visual defect.
- [x] Studio CI, Studio Visual Preview, Backend Architecture CI, and Required Check Compatibility all passed on the reviewed product head. REDGraft runtime deployment succeeded, but Modal again rejected the prefetch invocation because the configured workspace is disabled; this remains an external validation blocker, not an Item 08 regression.
- [x] Professional review result for Item 08: complete. No new checklist item required. **Item 09 is next and remains gated on user approval.**
'''
    if "### Iteration 8 — shared Image/Video AspectPicker" not in text:
        path.write_text(text + log + "\n")
    else:
        raise RuntimeError("Iteration 8 checklist log already exists")


def finalize_brief() -> None:
    replace_once(
        "docs/studio-ui-polish-iteration-brief.md",
        '''- Completed checklist items: **01–07**.\n- Next item: **08 — unify Image and Video aspect selection into one reusable `AspectPicker`**.\n- Do not begin Item 08 until the user says **continue**.\n- Development/review previews must remain GitHub-based; do not depend on Vercel previews during iteration.\n- Latest completed item is Iteration 7. Refinement run `32673600494` passed source validation, the poster/deferred-preview contract, build, and the full visual suite; artifact `9502051993` was professionally reviewed. The REDGraft Modal smoke remains externally blocked because the configured Modal workspace is disabled.\n''',
        '''- Completed checklist items: **01–08**.\n- Next item: **09 — standardize resolution terminology and expose actual delivery dimensions**.\n- Do not begin Item 09 until the user says **continue**.\n- Development/review previews must remain GitHub-based; do not depend on Vercel previews during iteration.\n- Latest completed item is Iteration 8. Final standard Studio Visual Preview run `32676390654` passed on reviewed product head `333e32236b116be9a48234abada56582cbfd6ff2`; artifact `9502799506` was professionally reviewed across Image, Video, Edit, mobile Create, and Gallery. Studio CI, Backend Architecture CI, and Required Check Compatibility also passed. The REDGraft Modal smoke remains externally blocked because the configured Modal workspace is disabled.\n''',
    )
    path = ROOT / "docs/studio-ui-polish-iteration-brief.md"
    text = path.read_text().rstrip()
    section = '''

### Iteration 8 — shared Image/Video AspectPicker

**Status:** complete.

**Implementation:** extracted `apps/studio/src/features/create/AspectPicker.jsx` as the reusable aspect-selection surface and canonical aspect-preset source. Image/Create, Edit, and Video now consume the same component. It owns the ratio-shape preview, option labels, menu radio semantics, keyboard navigation/selection, Escape and outside-focus dismissal, focus restoration, and viewport-aware fixed positioning. Video supplies optional Auto/reference state through props; Image uses the same component without an Auto option, while Edit exposes its reference-derived Auto state through the shared trigger.

**Deterministic coverage:** Create and Video visual scripts assert that both modes use the shared trigger/surface rather than independent implementations. Existing contracts continue to cover Arrow/Home/End navigation, Enter/Space selection, Escape focus return, focus-visible treatment, preview morphing, no unwanted menu scroll, Video Auto/manual transitions, reference inheritance/provenance, and mobile containment.

**Professional review cycle:** the first remote implementation run (`32675725844`) exposed a focus-handoff race when the shared menu mounted and attempted to focus its selected option; focus management was corrected instead of loosening the test. Refinement run `32675995131` then exposed a real 2px border-box overflow (`366` scroll height vs `364` client height); the menu height calculation was fixed while keeping the no-scroll assertion. Successful run `32676138933` produced the first fully green shared-component artifact (`9502718139`). Visual inspection then found that the default Video Auto provenance text was truncated inside the shared row. The row allocation and copy were refined to keep `16:9 · Follows reference` readable while retaining explicit `From reference` states.

**Visual review:** Image and Video now visibly use the same two-column picker with the same ratio preview, row density, selected/focused treatment, and complete 1:1–21:9 preset set. Video adds only the configured Auto row, rather than a parallel picker design. Edit's reference-driven Auto trigger is clear, the 390px Video toolbar remains contained, and Gallery/mobile regression screenshots remain stable. No remaining Item 08 visual defect was found.

**Validation:** final standard Studio Visual Preview run `32676390654` passed on reviewed product head `333e32236b116be9a48234abada56582cbfd6ff2`; artifact `9502799506` was inspected and recorded no page errors. Studio CI, Backend Architecture CI, and Required Check Compatibility also passed. REDGraft runtime deployment succeeded but Modal rejected the prefetch call with `ConflictError: workspace ... is disabled`, so that remains an external infrastructure blocker unrelated to this UI refactor.

**Professional review:** Item 08 is complete with no remaining actionable comments. Item 09 is next and remains gated on explicit user approval.
'''
    if "### Iteration 8 — shared Image/Video AspectPicker" not in text:
        path.write_text(text + section + "\n")
    else:
        raise RuntimeError("Iteration 8 brief section already exists")


if __name__ == '__main__':
    finalize_checklist()
    finalize_brief()
    print("Iteration 8 checklist and brief finalized")
