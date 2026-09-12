import assert from "node:assert/strict";
import test from "node:test";

import {
  validateWholeBookSuite,
  type WholeBookSuiteManifest,
} from "../src/evaluation/whole-book-benchmark.js";

function baseManifest(): WholeBookSuiteManifest {
  return {
    schemaVersion: "saga-whole-book-suite-v1",
    suiteId: "security-test",
    purpose: "verify benchmark output path isolation",
    sourcePolicy: "fixture only",
    books: [
      {
        id: "safe-book",
        title: "Safe Book",
        sourceFile: "safe.txt",
        sourceLocator: "fixture:safe",
        tags: ["fixture"],
        licenseNote: "fixture",
      },
    ],
  };
}

test("whole-book ids cannot contain traversal or path separators", () => {
  for (const unsafeId of ["../outside", "nested/book", "nested\\book", ".", "..", "book with space"]) {
    const candidate = baseManifest();
    candidate.books[0]!.id = unsafeId;
    assert.throws(
      () => validateWholeBookSuite(candidate),
      /unsafe_whole_book_id/,
      unsafeId,
    );
  }
});

test("whole-book source path cannot resolve to the source root itself", () => {
  const candidate = baseManifest();
  candidate.books[0]!.sourceFile = ".";
  assert.throws(
    () => validateWholeBookSuite(candidate),
    /unsafe_whole_book_source_path:safe-book/,
  );
});
