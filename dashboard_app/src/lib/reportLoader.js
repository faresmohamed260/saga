export async function loadMarkdownFile(fileHandle) {
  const file = await fileHandle.getFile();
  return file.text();
}

export function summarizeMarkdown(markdownText) {
  const lines = String(markdownText || "").split(/\r?\n/);
  const title = lines.find((line) => line.trim().startsWith("#"))?.replace(/^#+\s*/, "") || "";
  const headings = lines.filter((line) => line.trim().startsWith("#")).length;
  return {
    title,
    headings,
    lineCount: lines.length,
  };
}
