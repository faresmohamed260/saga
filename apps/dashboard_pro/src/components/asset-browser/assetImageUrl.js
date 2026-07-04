export function assetImageUrl(path) {
  return path ? `/runtime/file?path=${encodeURIComponent(path)}` : "";
}
