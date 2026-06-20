import { Cormorant_Garamond } from "next/font/google";
import BottomBox from "./bottomBox";
import star from "@/public/star.png";
import Image from "next/image";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function RightBox({
  num1,
  num2,
  imageUrl,
  title,
  description,
  status,
  onSave,
  canSave,
  saving,
  galleryItems,
  selectedGalleryId,
  onSelectGallery,
  renderStatus,
}) {
  return (
    <div className="flex w-full max-w-[560px] flex-col gap-10">
      <div className="rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] px-6 py-5 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#6745af] p-1.5">
            {num1}
          </span>
          <p className={`${cormorant.className} text-[25px]`}>
            Generated Visuals
          </p>
        </div>
        <p className="mt-4 max-w-[420px] text-sm text-white/70">
          {description || "Your AI-generated visuals will appear here."}
        </p>

        <div
          className="relative mt-6 overflow-hidden rounded-2xl"
          style={{
            border: "1px solid rgba(180, 160, 255, 0.25)",
            background: "rgba(10, 5, 30, 0.8)",
          }}
        >
          <div className="aspect-[5/4] w-full">
            {imageUrl ? (
              <img
                src={imageUrl}
                alt={title || "Generated visual"}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center px-8 text-center text-white/35">
                Select a story asset and generate a preview to populate this panel.
              </div>
            )}
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className={`${cormorant.className} text-xl text-white`}>
              {title || "No visual selected"}
            </p>
            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-white/45">
              {renderStatus || "preview pending"}
            </p>
          </div>

          <button
            onClick={onSave}
            disabled={!canSave || saving}
            className="rounded-full px-6 py-2 text-sm text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              background:
                "linear-gradient(to right, rgba(93, 56, 167, 0), rgba(102, 102, 102, 0.45))",
              border: "1px solid rgba(180, 160, 255, 0.5)",
              boxShadow:
                "0 0 15px rgba(180, 160, 255, 0.4), 0 0 30px rgba(180, 160, 255, 0.2)",
            }}
          >
            {saving ? "Saving..." : "Save to Library"}
          </button>
        </div>

        {status ? <p className="mt-4 text-sm text-white/65">{status}</p> : null}
      </div>

      <BottomBox
        num={num2}
        items={galleryItems}
        selectedId={selectedGalleryId}
        onSelect={onSelectGallery}
      />

      <div className="mt-[20px] flex items-center justify-center flex-col">
        <p className="text-xs text-white/50 ">
          Visualize Your Imagination, Instantly
        </p>
        <div className="flex items-center ">
          <div className="w-32 h-[1px] bg-[#FFC120]" />

          <div className="w-[60px] h-[70px] mx-[-10px] pb-6 flex items-center justify-center">
            <Image src={star} alt="star" />
          </div>

          <div className="w-32 h-[1px] bg-[#FFC120]" />
        </div>
      </div>
    </div>
  );
}
