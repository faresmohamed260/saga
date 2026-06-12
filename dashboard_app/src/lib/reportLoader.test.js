import { expect, test } from "vitest";
import { summarizeMarkdown } from "./reportLoader";

test("summarizeMarkdown extracts title and heading count", () => {
  const summary = summarizeMarkdown("# Main Title\n\n## Section\nText");
  expect(summary.title).toBe("Main Title");
  expect(summary.headings).toBe(2);
});
