import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function BottomBox({ num, items, selectedId, onSelect }) {
  const galleryItems = Array.isArray(items) ? items.slice(0, 4) : [];

  return (
    <div className="w-full rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] px-6 py-5 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#6745af] p-1.5">
          {num}
        </span>
        <p className={`${cormorant.className} text-[25px]`}>Book Gallery</p>
      </div>

      <p className="mb-8 mt-4 max-w-[300px] text-sm text-white/70">
        More variations based on your prompt
      </p>

      <div className="flex flex-wrap items-center gap-4">
        {galleryItems.length ? (
          galleryItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelect?.(item.id)}
              className={`h-[100px] w-[100px] flex-shrink-0 overflow-hidden rounded-2xl transition ${
                selectedId === item.id ? "ring-2 ring-[#FFC120]" : ""
              }`}
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(180,160,255,0.2)",
              }}
            >
              {item.thumbnailUrl ? (
                <img
                  src={item.thumbnailUrl}
                  alt={item.label || "Gallery image"}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center px-2 text-center text-[10px] text-white/40">
                  No image
                </div>
              )}
            </button>
          ))
        ) : (
          [1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-[100px] w-[100px] flex-shrink-0 rounded-2xl"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(180,160,255,0.2)",
              }}
            />
          ))
        )}
      </div>
    </div>
  );
}
