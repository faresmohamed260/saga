import { StatusBanner } from "../primitives";

export function AudiobookNotice({ notice }) {
  if (!notice?.text) return null;
  return <StatusBanner tone={notice.tone} message={notice.text} />;
}
