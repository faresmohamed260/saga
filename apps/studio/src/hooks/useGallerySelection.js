import { useEffect, useMemo, useState } from 'react';

export default function useGallerySelection(items) {
  const [managing, setManaging] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [actionBusy, setActionBusy] = useState('');
  const itemIds = useMemo(() => new Set(items.map((item) => item.id)), [items]);

  useEffect(() => {
    setSelected((current) => {
      const next = new Set([...current].filter((id) => itemIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [itemIds]);

  const selectedItems = useMemo(() => items.filter((item) => selected.has(item.id)), [items, selected]);
  const toggle = (item) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
    return next;
  });
  const finishManaging = () => { setManaging(false); setSelected(new Set()); };
  const runBulk = async (name, callback) => {
    if (!selectedItems.length || actionBusy) return;
    setActionBusy(name);
    try {
      const result = await callback?.(selectedItems);
      if (result && Array.isArray(result.failedIds)) setSelected(new Set(result.failedIds));
      else if ((name === 'delete' || name === 'collection') && result !== false) setSelected(new Set());
    } finally { setActionBusy(''); }
  };
  return { managing, setManaging, selected, setSelected, actionBusy, selectedItems, toggle, finishManaging, runBulk };
}
