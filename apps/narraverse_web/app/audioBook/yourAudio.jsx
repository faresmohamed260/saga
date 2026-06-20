"use client";

import RightBox from "./boxes/rightbox";
import TopBox from "./boxes/topBox";
import BottomBomx from "./boxes/bottomBox";
import star from "@/public/star.png";
import Image from "next/image";
import { useSearchParams } from "next/navigation";

export default function YourAudio() {
  const searchParams = useSearchParams();
  const from = searchParams.get("from");

  const showLeftBox = from === "services";

  return (
    <div className="relative z-10 flex justify-end gap-14 pb-[100px] pr-16">
      <div>
        {showLeftBox && <TopBox num="1" />}
        <BottomBomx num={showLeftBox ? "2" : "1"} />
      </div>
      <div>
        <RightBox num={showLeftBox ? "3" : "2"} />
        <div className="mt-[200px] flex justify-center items-center flex-col">
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
    </div>
  );
}
