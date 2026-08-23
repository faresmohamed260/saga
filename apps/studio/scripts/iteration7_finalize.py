from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}\n{old[:1000]}")
    path.write_text(text.replace(old, new, 1))


def finalize_checklist() -> None:
    path = ROOT / "docs/studio-ui-polish-checklist.md"
    replace_once(
        path,
        '''**Iteration 7 — unified Video Aspect control**\n\n- Status: `[~]` in progress\n- Working item: **07**\n- Rule: replace the separate Auto + ratio controls with one explicit Aspect control that exposes automatic/manual mode, effective ratio, and reference provenance; preserve keyboard behavior and validate desktop/mobile GitHub visual previews before completion.\n''',
        '''**Iteration 7 — unified Video Aspect control**\n\n- Status: `[x]` complete\n- Completed item: **07**\n- Next item: **08 — unify Image and Video aspect selection into one reusable `AspectPicker`**\n- Rule: do not start Item 08 until the user explicitly says continue. Each future iteration must follow implement → deterministic test → GitHub CI/visual preview → inspect screenshots → professional critique → record improvements → update this file → stop for user approval.\n''',
    )
    replace_once(
        path,
        '- [~] **07. Merge Auto + aspect ratio into one clear Aspect control.** Example states: `Aspect · Auto 16:9`, `Aspect · Auto 4:3 · From reference`, or manual ratio. **Iteration 7 in progress.**\n',
        '- [x] **07. Merge Auto + aspect ratio into one clear Aspect control.** Video now exposes one Aspect picker that combines Auto/manual mode, effective ratio, and reference provenance in a single trigger/menu while preserving keyboard behavior. **Iteration 7 complete.**\n',
    )
    text = path.read_text()
    heading = '### Iteration 7 — unified Video Aspect control'
    if heading in text:
        raise RuntimeError('Checklist already contains an Iteration 7 completion log')
    log = '''### Iteration 7 — unified Video Aspect control\n\n- [x] Removed the separate Video `Auto` button; Video output now exposes only a unified Aspect picker plus FPS in the extra-controls group.\n- [x] Unified trigger states communicate mode and effective value directly: `Aspect · Auto 16:9`, `Aspect · Auto 4:3 · From reference`, and manual states such as `Aspect · 9:16`.\n- [x] Auto is the first radio option inside the same Aspect menu; choosing it restores reference-following behavior, while choosing any ratio switches to manual mode.\n- [x] Preserved the existing exact reduced reference ratio, 16:9 fallback, persisted settings, generated `videoAspectMode`, and Item 04 keyboard contract (Arrow navigation, Home/End, Enter/Space, Escape, focus return).\n- [x] Added deterministic assertions that no separate Auto control remains, Aspect + FPS are the only Video extra controls, Auto is selected by default, manual selection exits Auto, reference provenance is visible, mobile layout is not clipped, and the mobile Aspect menu stays inside the viewport.\n- [x] First professional visual review found two Item 07 issues: the trigger abbreviated reference provenance as `Ref`, and adding Auto made the final `21:9 Cinematic` option partially hidden behind the desktop menu scroll boundary.\n- [x] Refinement changed the visible state to the full `From reference` wording and gave the desktop Aspect menu enough height to show all twelve choices without scrolling; mobile retains viewport-safe scrolling.\n- [x] Initial implementation/review run `32673410326` passed and produced artifact `9502002385`; refinement run `32673600494` passed source validation, poster/deferred-preview contract, build, full visual suite, and artifact upload `9502051993`.\n- [x] Final professional visual review confirmed the unified control is clearer, all desktop Aspect choices are visible, reference provenance is explicit, keyboard focus remains strong, and the mobile control/menu geometry is not clipped.\n- [x] Refined product head: `93c4f7005ee651778775fb217892558487c1ede3`.\n- [x] Professional review result for Item 07: complete. No new checklist item required. **Item 08 is next and remains gated on user approval.**'''
    path.write_text(text.rstrip() + '\n\n' + log + '\n')


def finalize_brief() -> None:
    path = ROOT / "docs/studio-ui-polish-iteration-brief.md"
    replace_once(path, '- Completed checklist items: **01–06**.\n', '- Completed checklist items: **01–07**.\n')
    replace_once(
        path,
        '- Next item: **07 — merge Auto + aspect ratio into one clear Aspect control**.\n',
        '- Next item: **08 — unify Image and Video aspect selection into one reusable `AspectPicker`**.\n',
    )
    replace_once(
        path,
        '- Do not begin Item 07 until the user says **continue**.\n',
        '- Do not begin Item 08 until the user says **continue**.\n',
    )
    replace_once(
        path,
        '- Latest completed item is Iteration 6. Final refinement run `32671818722` passed the deferred-preview contract, build, and full visual suite; artifact `9501593078` was professionally reviewed. The REDGraft Modal smoke remains externally blocked because the configured Modal workspace is disabled.\n',
        '- Latest completed item is Iteration 7. Refinement run `32673600494` passed source validation, the poster/deferred-preview contract, build, and the full visual suite; artifact `9502051993` was professionally reviewed. The REDGraft Modal smoke remains externally blocked because the configured Modal workspace is disabled.\n',
    )
    replace_once(
        path,
        'Remaining high-value work includes clearer Auto/aspect controls, shared aspect-picker architecture, consistent resolution terminology, stronger Generate/audio affordances, richer real lifecycle feedback, bulk-management improvements, Create composition refactoring, Gallery naming/internal cleanup, App.jsx responsibility reduction, card metadata simplification, search/sort, design-token consolidation, broader accessibility, and true screenshot-baseline regression testing.',
        'Remaining high-value work includes shared Image/Video aspect-picker architecture, consistent resolution terminology, stronger Generate/audio affordances, richer real lifecycle feedback, bulk-management improvements, Create composition refactoring, Gallery naming/internal cleanup, App.jsx responsibility reduction, card metadata simplification, search/sort, design-token consolidation, broader accessibility, and true screenshot-baseline regression testing.',
    )
    text = path.read_text()
    heading = '### Iteration 7 — unified Video Aspect control'
    if heading in text:
        raise RuntimeError('Brief already contains an Iteration 7 log')
    log = '''### Iteration 7 — unified Video Aspect control\n\n**Status:** complete.\n\n**Implementation:** replaced the separate Video Auto toggle plus ratio picker with one Aspect picker. Its trigger communicates automatic/manual mode and the effective ratio directly, including full reference provenance (`Aspect · Auto 4:3 · From reference`). The menu places Auto alongside the manual ratio choices; Auto follows the first reference when present and falls back to 16:9, while any explicit ratio switches to manual mode. Existing persistence and generation payload semantics remain unchanged.\n\n**Deterministic coverage:** the Video-output Playwright suite now rejects any separate Auto button, requires exactly Aspect + FPS extra controls, verifies default Auto selection, keyboard navigation to manual 9:16, returning to Auto through the same menu, reference-derived 4:3 state, 16:9 fallback after reference removal, complete desktop option visibility, mobile trigger containment, and mobile menu viewport containment.\n\n**Professional review cycle:** the first visual review accepted the combined-control direction but rejected two details: `Ref` was too abbreviated for a primary state label, and the new Auto row pushed `21:9 Cinematic` partly behind the desktop menu scroll boundary. The refinement uses the full `From reference` wording and a desktop-only Aspect-menu height that exposes all twelve choices without scrolling while preserving the viewport-safe mobile cap.\n\n**Visual review:** the final desktop trigger/menu, reference-derived state, keyboard-focus state, and 390px mobile state were inspected. The control reads as one coherent setting, reference provenance is explicit, all desktop choices are visible, and mobile layout remains unclipped. No additional Item 07 defect remains.\n\n**Validation:** dedicated refinement run `32673600494` passed source formatting, `npm run test:poster`, Studio build, the full `visual:preview` suite, and artifact upload (`9502051993`). Refined product head `93c4f7005ee651778775fb217892558487c1ede3`. Item 08 is next and remains gated on explicit user approval.'''
    path.write_text(text.rstrip() + '\n\n' + log + '\n')


def main() -> None:
    finalize_checklist()
    finalize_brief()
    print('Iteration 7 documentation finalized')


if __name__ == '__main__':
    main()
