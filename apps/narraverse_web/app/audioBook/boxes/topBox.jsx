"use client";

import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function TopBox({ num }) {
  return (
    <div className=" rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] py-5 px-10  w-fit h-fit">
      <div className="flex items-center gap-6 justify-center">
        <span className="border border-transparent p-1.5 bg-[#6745af] w-7 h-7 rounded-full  flex items-center justify-center">
          {num}
        </span>
        <p className={`${cormorant.className} text-[25px]`}>
          Your Original Story
        </p>
      </div>

      <div className="mt-[30px]">
        <p className="text-white/70 mb-5">Upload your story </p>
        <label className="flex gap-3 items-center justify-center w-full py-3 cursor-pointer rounded-xl border-2 border-dashed border-[rgba(180,160,255,0.4)]">
          <input type="file" className="hidden" accept=".txt,.pdf,.docx" />
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-6 h-6 text-white mb-1"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 12V4m0 0L8 8m4-4l4 4"
            />
          </svg>
          <span className="text-white font-semibold">Upload file</span>
        </label>
        <p className="flex justify-center mt-3 text-sm text-white/70">
          Supports: .txt, .pdf, .docx
        </p>
      </div>
    </div>
  );
}
