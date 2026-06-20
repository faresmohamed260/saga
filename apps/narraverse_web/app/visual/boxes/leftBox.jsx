"use client";

import { Cormorant_Garamond } from "next/font/google";
import { faLightbulb } from "@fortawesome/free-regular-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function LeftBox({
  num,
  seriesOptions,
  selectedSeriesId,
  onSeriesChange,
  entityType,
  onEntityTypeChange,
  searchQuery,
  onSearchChange,
  entityOptions,
  selectedEntityId,
  onEntityChange,
  promptDraft,
  onPromptDraftChange,
  bookTitle,
  loadingSeries,
  loadingEntities,
  loadingAsset,
  onGenerate,
  generating,
  disabled,
  helperText,
}) {
  return (
    <div className="flex w-full max-w-[390px] flex-col items-center">
      <div className="w-full rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] px-6 py-5 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#6745af] p-1.5">
            {num}
          </span>
          <p className={`${cormorant.className} text-[25px]`}>
            Your Story Asset
          </p>
        </div>

        <div className="mt-6 space-y-4 text-white/80">
          <div>
            <p className="mb-2 text-sm text-white/70">Choose a story universe</p>
            <select
              value={selectedSeriesId}
              onChange={(event) => onSeriesChange(event.target.value)}
              disabled={loadingSeries}
              className="w-full rounded-xl border border-[rgba(180,160,255,0.25)] bg-[rgba(15,10,40,0.88)] px-4 py-3 text-sm text-white outline-none disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loadingSeries ? (
                <option value="">Loading story universes...</option>
              ) : null}
              {seriesOptions.map((series) => (
                <option key={series.series_id} value={series.series_id}>
                  {series.series_title}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm text-white/70">
                Asset type
              </span>
              <select
                value={entityType}
                onChange={(event) => onEntityTypeChange(event.target.value)}
                className="w-full rounded-xl border border-[rgba(180,160,255,0.25)] bg-[rgba(15,10,40,0.88)] px-4 py-3 text-sm text-white outline-none"
              >
                <option value="">All assets</option>
                <option value="character">Characters</option>
                <option value="location">Locations</option>
                <option value="object">Objects</option>
                <option value="creature">Creatures</option>
              </select>
            </label>

            <label className="block">
              <span className="mb-2 block text-sm text-white/70">
                Search name
              </span>
              <input
                type="text"
                value={searchQuery}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder="Harry, Hogwarts, wand..."
                className="w-full rounded-xl border border-[rgba(180,160,255,0.25)] bg-[rgba(15,10,40,0.88)] px-4 py-3 text-sm text-white outline-none placeholder:text-white/35"
              />
            </label>
          </div>

          <div>
            <p className="mb-2 text-sm text-white/70">Select a backend asset</p>
            <select
              value={selectedEntityId}
              onChange={(event) => onEntityChange(event.target.value)}
              disabled={loadingEntities || loadingAsset}
              className="w-full rounded-xl border border-[rgba(180,160,255,0.25)] bg-[rgba(15,10,40,0.88)] px-4 py-3 text-sm text-white outline-none disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loadingEntities ? (
                <option value="">Loading backend assets...</option>
              ) : entityOptions.length ? null : (
                <option value="">No matching assets found</option>
              )}
              {entityOptions.map((entity) => (
                <option key={entity.id} value={entity.id}>
                  {entity.name} - {entity.entity_type} - {entity.book_title}
                </option>
              ))}
            </select>
            {bookTitle ? (
              <p className="mt-2 text-xs text-white/55">Source: {bookTitle}</p>
            ) : null}
          </div>

          <div>
            <p className="mb-2 text-sm text-white/70">Visual direction</p>
            <textarea
              value={promptDraft}
              onChange={(event) => onPromptDraftChange(event.target.value)}
              rows={6}
              disabled={loadingAsset}
              placeholder="Prompt details from the existing backend asset will appear here."
              className="w-full resize-none rounded-xl border border-[rgba(180,160,255,0.25)] bg-[rgba(15,10,40,0.88)] px-4 py-3 text-sm text-white outline-none placeholder:text-white/35 disabled:cursor-not-allowed disabled:opacity-70"
            />
          </div>
        </div>
      </div>

      <div className="my-6 flex justify-center">
        <button
          onClick={onGenerate}
          disabled={disabled || generating}
          className="rounded-full px-[50px] py-2 text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            background:
              "linear-gradient(to right, rgba(93, 56, 167, 0), rgba(102, 102, 102, 0.45))",
            border: "1px solid rgba(180, 160, 255, 0.5)",
            boxShadow:
              "0 0 15px rgba(180, 160, 255, 0.4), 0 0 30px rgba(180, 160, 255, 0.2)",
          }}
        >
          {generating ? "Generating..." : "Generate Visuals"}
        </button>
      </div>

      <div
        className="relative w-full rounded-2xl px-6 py-5"
        style={{
          background: "rgba(0,0,0,0.4)",
          border: "1px solid rgba(255,255,255,0.15)",
          boxShadow: "inset 0 0 30px rgba(0,0,0,0.5)",
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100%25' height='100%25'%3E%3Crect width='100%25' height='100%25' fill='none' stroke='rgba(255,255,255,0.2)' stroke-width='2' stroke-dasharray='6 4' rx='16'/%3E%3C/svg%3E\")",
        }}
      >
        <div className="mb-3 flex items-center gap-2">
          <FontAwesomeIcon icon={faLightbulb} className="text-white" width={20} />
          <p className={`${cormorant.className} text-xl text-white`}>AI Tips</p>
        </div>

        <p className="text-sm leading-relaxed text-white/60">
          {helperText ||
            "Pick an analyzed story asset from the S.A.G.A. backend, refine its prompt, and generate a new preview without changing the backend contract."}
        </p>
      </div>
    </div>
  );
}
