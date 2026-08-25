from pathlib import Path

path = Path('scripts/studio_advanced_ui_audit_patch.py')
text = path.read_text(encoding='utf-8')
old = '''            "import React, { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';",
            "import React, { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';\\nimport { createPortal } from 'react-dom';",
'''
new = '''            "} from 'react';",
            "} from 'react';\\nimport { createPortal } from 'react-dom';",
'''
if text.count(old) != 1:
    raise SystemExit(f'Expected one helper import patch target, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
