import { Cormorant_Garamond } from "next/font/google";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faFloppyDisk, faClone } from "@fortawesome/free-regular-svg-icons";
import { Roboto } from "next/font/google";
import { faLightbulb } from "@fortawesome/free-regular-svg-icons";
import star from "@/public/star.png";
import Image from "next/image";
import Link from "next/link";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
});

export default function GeneratedBook() {
  return (
    <div className="relative z-10 ">
      <div className="flex justify-around pb-[50px]">
        <div className=" rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] py-5 px-10 w-full h-fit mr-[80px] ml-[300px]">
          <div className="flex items-center gap-6 justify-center">
            <span className="border border-transparent p-1.5 bg-[#6745af] w-7 h-7 rounded-full  flex items-center justify-center">
              4
            </span>
            <p className={`${cormorant.className} text-[25px]`}>
              Generated Book
            </p>
          </div>

          <p className="text-white/70 text-sm mb-8 mt-4 flex justify-center">
            Your AI-generated book will appear here
          </p>

          <div
            className="relative w-full h-[400px] rounded-2xl flex items-center justify-center mb-6"
            style={{
              border: "1px solid rgba(180, 160, 255, 0.25)",
              background: "rgba(10, 5, 30, 0.8)",
            }}
          >
            <p
              className={`${cormorant.className} text-2xl text-white/40 tracking-widest`}
            >
              Your Next Chapter Awaits....
            </p>
          </div>

          <div className="flex justify-end gap-8 mr-4">
            <button
              className="cursor-pointer flex items-center gap-2 px-6 py-1.5 rounded-xl"
              style={{
                border: "1px solid rgba(180, 160, 255, 0.25)",
                background: "rgba(10, 5, 30, 0.8)",
              }}
            >
              <FontAwesomeIcon icon={faFloppyDisk} />
              <p className={roboto.className}>Save to Library</p>
            </button>

            <button
              className="cursor-pointer flex items-center gap-2 px-6 py-1.5 rounded-xl"
              style={{
                border: "1px solid rgba(180, 160, 255, 0.25)",
                background: "rgba(10, 5, 30, 0.8)",
              }}
            >
              <FontAwesomeIcon icon={faClone} />
              <p className={roboto.className}>Copy to Clipboard</p>
            </button>
          </div>
        </div>
      </div>
      <div className="flex justify-center pb-[30px] gap-12 ml-[350px]">
        <button
          className="px-[100px] py-2 rounded-full text-white cursor-pointer"
          style={{
            background:
              "linear-gradient(to right, rgba(93, 56, 167, 0), rgba(102, 102, 102, 0.45))",
            border: "1px solid rgba(180, 160, 255, 0.5)",
            boxShadow:
              "0 0 15px rgba(180, 160, 255, 0.4), 0 0 30px rgba(180, 160, 255, 0.2)",
          }}
        >
          <Link href="/visual?from=generatedBook">Generate Visuals</Link>
        </button>
        <button
          className="px-[100px] py-2 rounded-full text-white cursor-pointer"
          style={{
            background:
              "linear-gradient(to right, rgba(93, 56, 167, 0), rgba(102, 102, 102, 0.45))",
            border: "1px solid rgba(180, 160, 255, 0.5)",
            boxShadow:
              "0 0 15px rgba(180, 160, 255, 0.4), 0 0 30px rgba(180, 160, 255, 0.2)",
          }}
        >
          <Link href="/audioBook?from=generatedBook">Generate Audio</Link>
        </button>
      </div>

      <div className="flex flex-col items-center justify-center pt-[150px] pb-[200px] ml-[350px]">
        <div
          className="relative px-8 py-6 rounded-2xl w-fit"
          style={{
            background: "rgba(0,0,0,0.4)",
            border: "1px solid rgba(255,255,255,0.15)",
            boxShadow: "inset 0 0 30px rgba(0,0,0,0.5)",
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100%25' height='100%25'%3E%3Crect width='100%25' height='100%25' fill='none' stroke='rgba(255,255,255,0.2)' stroke-width='2' stroke-dasharray='6 4' rx='16'/%3E%3C/svg%3E")`,
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <FontAwesomeIcon icon={faLightbulb} className="text-white" />
            <p className={`${cormorant.className} text-white text-xl`}>
              AI Tips
            </p>
          </div>

          <p className="text-white/60 text-sm leading-relaxed">
            The more details you provide, the better and more unique your sequel
            will be!
          </p>
        </div>

        <div className="mt-[50px]">
          <p>Every Great Story Begins with a Single Step</p>
          <div className="flex items-center ">
            <div className="w-32 h-[1px] bg-[#FFC120]" />

            <div className="w-[70px] h-[90px] mx-[-10px] pb-6 flex items-center justify-center">
              <Image src={star} alt="star" />
            </div>

            <div className="w-32 h-[1px] bg-[#FFC120]" />
          </div>
        </div>
      </div>
    </div>
  );
}
