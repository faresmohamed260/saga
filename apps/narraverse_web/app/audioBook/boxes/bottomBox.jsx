import { Cormorant_Garamond } from "next/font/google";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faChevronDown } from "@fortawesome/free-solid-svg-icons";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function BottomBox({ num }) {
  return (
    <div className="flex flex-col justify-between mt-8">
      <div className=" rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] py-5 px-10 w-[327px] h-fit">
        <div className="flex items-center gap-6 justify-center">
          <span className="border border-transparent p-1.5 bg-[#6745af] w-7 h-7 rounded-full  flex items-center justify-center">
            {num}
          </span>
          <p className={`${cormorant.className} text-[22px]`}>
            Select Narration Type
          </p>
        </div>

        <div>
          <p className="text-white/70 text-sm mb-8 mt-4">
            Select the type of narration you want your audio book to be.
          </p>
          <div className="relative mb-10">
            <div className="relative">
              <select className="w-full bg-[rgba(255,255,255,0.05)] border border-[rgba(180,160,255,0.25)] rounded-xl px-4 py-4 text-white appearance-none outline-none cursor-pointer">
                <option value="classic" className="bg-[#1a1a2e]">
                  Classic
                </option>
                <option value="epic" className="bg-[#1a1a2e]">
                  Epic
                </option>
                <option value="dramatic" className="bg-[#1a1a2e]">
                  Dramatic
                </option>
              </select>

              <FontAwesomeIcon
                icon={faChevronDown}
                width={20}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white/50 pointer-events-none"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-center my-[30px]">
        <button
          className="px-[50px] py-2 rounded-full text-white cursor-pointer"
          style={{
            background:
              "linear-gradient(to right, rgba(93, 56, 167, 0), rgba(102, 102, 102, 0.45))",
            border: "1px solid rgba(180, 160, 255, 0.5)",
            boxShadow:
              "0 0 15px rgba(180, 160, 255, 0.4), 0 0 30px rgba(180, 160, 255, 0.2)",
          }}
        >
          Generate Audio
        </button>
      </div>
    </div>
  );
}
