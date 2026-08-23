import fs from 'node:fs';

const path = 'apps/studio/src/app/App.jsx';
let source = fs.readFileSync(path, 'utf8');
source = source.replace("const navPrimary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [History, 'History'], [Heart, 'Favorites'], [Folder, 'Collections']];\nconst navSecondary = [[Box, 'Models'], [Workflow, 'Workflows']];\n\n", '');
source = source.replace("function formatJobTime(value) {\n  if (!value) return '—';\n  const date = new Date(value);\n  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();\n}\n\n", '');
source = source.replace("function NavItem({ icon: Icon, label, active, onClick }) {\n  return <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;\n}\n\n", '');
fs.writeFileSync(path, source, 'utf8');
console.log('Removed legacy navigation helpers from App.jsx');
