"use client";

import { Cormorant_Garamond } from "next/font/google";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faChevronDown } from "@fortawesome/free-solid-svg-icons";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function LeftBox() {
  return (
    <div className=" rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] py-5 px-10  w-fit h-fit">
      <div className="flex items-center gap-6 justify-center">
        <span className="border border-transparent p-1.5 bg-[#6745af] w-7 h-7 rounded-full  flex items-center justify-center">
          1
        </span>
        <p className={`${cormorant.className} text-[25px]`}>
          Your Original Story
        </p>
      </div>

      <div className="mt-[30px]">
        <p className="text-white/70 mb-5">Upload your story </p>
        <label className="flex items-center justify-center w-full py-3 cursor-pointer rounded-xl border-2 border-dashed border-[rgba(180,160,255,0.4)]">
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
          Supports: .txt, .pdf, .docx{" "}
        </p>
      </div>

      <div className="flex items-center gap-4 my-4">
        <hr className="flex-1 border-white/70" />
        <span className="text-white/70 text-sm whitespace-nowrap">
          or choose an existing book
        </span>
        <hr className="flex-1 border-white/70" />
      </div>

      <div className="relative">
        <select className="w-full bg-[rgba(255,255,255,0.05)] border border-[rgba(180,160,255,0.25)] rounded-xl px-4 py-4 text-white appearance-none outline-none cursor-pointer">
          <option value="harry-potter" className="bg-[#1a1a2e] text-white/70">
            Harry Potter
          </option>
          <option value="aCOTAR" className="bg-[#1a1a2e] text-white/70">
            ACOTAR
          </option>
          <option
            value="folk-of-the-air"
            className="bg-[#1a1a2e] text-white/70"
          >
            Folk of the Air
          </option>
          <option value="caraval" className="bg-[#1a1a2e] text-white/70">
            Caraval
          </option>
        </select>

        <FontAwesomeIcon
          icon={faChevronDown}
          className="absolute right-4 top-1/2 -translate-y-1/2 text-white/50 pointer-events-none"
        />
      </div>
    </div>
  );
}
