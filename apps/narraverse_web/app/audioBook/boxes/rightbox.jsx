import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function RighttBox({ num }) {
  return (
    <div className="relative z-10 flex justify-end gap-5 pb-[100px] pr-16">
      <div className=" rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] py-5 px-10 w-fit h-fit">
        <div className="flex items-center gap-6 ">
          <span className="border border-transparent p-1.5 bg-[#6745af] w-7 h-7 rounded-full  flex items-center justify-center">
            {num}
          </span>
          <p className={`${cormorant.className} text-[25px]`}>
            Generated Audio
          </p>
        </div>
        <p className="text-white/70 text-sm mb-8 mt-4 max-w-[300px]">
          Your AI-generated narrated chapters will appear here.
        </p>

        <div
          className="relative w-[400px] h-[400px] rounded-2xl flex items-center justify-center mb-6"
          style={{
            border: "1px solid rgba(180, 160, 255, 0.25)",
            background: "rgba(10, 5, 30, 0.8)",
          }}
        ></div>
      </div>
    </div>
  );
}
