export function modelDisplayName(value) {
  const model = String(value || '').trim();
  if (!model) return 'Unknown model';
  if (/flux\.2\s+klein\s+9b/i.test(model) || /darkbeast/i.test(model)) return 'FLUX.2 Klein 9B';
  if (/ltx\s*2\.5/i.test(model) || /sulphur2/i.test(model) || /redgraft/i.test(model)) return 'LTX Video 2.5';
  return model;
}

export function modelImplementationLabel(value) {
  return String(value || '').trim();
}
