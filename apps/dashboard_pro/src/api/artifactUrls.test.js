import { describe, expect, test } from "vitest";
import { artifactUrl, audiobookRunBundleUrl } from "./artifactUrls";

describe("artifactUrl", () => {
  test("supports explicit runtime urls", () => {
    expect(artifactUrl({ runtime_url: "/runtime/artifacts/object?bucket_name=generated-images&object_path=series/x/assets/y/file.png" }))
      .toBe("/runtime/artifacts/object?bucket_name=generated-images&object_path=series/x/assets/y/file.png");
  });

  test("supports bucket/object references", () => {
    expect(artifactUrl({ bucket_name: "generated-images", object_path: "series/x/assets/y/file.png" }))
      .toBe("/runtime/artifacts/object?bucket_name=generated-images&object_path=series%2Fx%2Fassets%2Fy%2Ffile.png");
  });

  test("does not accept legacy file paths", () => {
    expect(artifactUrl("B:/images/entity.png")).toBe("");
  });
});

describe("audiobookRunBundleUrl", () => {
  test("prefers explicit bundle artifacts", () => {
    expect(audiobookRunBundleUrl({
      id: "run-1",
      bundle_artifact: { bucket_name: "audio-outputs", object_path: "series/x/audio/runs/run-1/full.wav" },
    })).toBe("/runtime/artifacts/object?bucket_name=audio-outputs&object_path=series%2Fx%2Faudio%2Fruns%2Frun-1%2Ffull.wav");
  });

  test("falls back to runtime run audio endpoint", () => {
    expect(audiobookRunBundleUrl("run-1")).toBe("/runtime/audiobook/runs/run-1/audio");
  });
});
