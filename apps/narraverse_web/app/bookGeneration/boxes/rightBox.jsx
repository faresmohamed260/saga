import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function RightBox() {
  return (
    <div className=" rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] py-5 px-10 w-fit h-fit">
      <div className="flex items-center gap-6 justify-center">
        <span className="border border-transparent p-1.5 bg-[#6745af] w-7 h-7 rounded-full  flex items-center justify-center">
          3
        </span>
        <p className={`${cormorant.className} text-[25px]`}>Narrative Prompt</p>
      </div>
      <p className="text-white/70 text-sm mb-8 mt-4 max-w-[300px]">
        Create your own story by defining characters, style, setting, tone, key
        events, and the tropes that shape the narrative.
      </p>

      <div className="pb-5">
        <textarea
          maxLength={50000}
          placeholder="Enter prompt.."
          className="w-full h-[300px] bg-black/5 border border-[rgba(180,160,255,0.25)] rounded-xl p-3 text-white placeholder:text-white/70 resize-none outline-none"
        />
      </div>
    </div>
  );
}
