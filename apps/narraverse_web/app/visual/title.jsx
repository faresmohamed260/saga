import { Cormorant_Garamond } from "next/font/google";
import star from "@/public/star.png";
import Image from "next/image";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function Title() {
  return (
    <div className="relative z-10 flex flex-col items-center justify-center px-8 pt-[100px]">
      <h1
        className={`${cormorant.className} text-center text-4xl leading-tight text-white sm:text-5xl lg:text-6xl`}
      >
        Create Your
        <span className="bg-gradient-to-r from-[rgba(255,193,32,0.69)] via-[#FFC120] to-[rgba(183,137,17,0.69)] bg-clip-text pl-3 text-transparent">
          Visuals
        </span>
      </h1>

      <div className="flex items-center">
        <div className="h-[1px] w-[100px] bg-[#FFC120] sm:w-[150px] lg:w-[200px]" />

        <div className="mx-[-12px] flex h-[88px] w-[88px] items-center justify-center pb-6 sm:mx-[-16px] sm:h-[104px] sm:w-[104px] lg:mx-[-20px] lg:h-[118px] lg:w-[120px]">
          <Image src={star} alt="star" />
        </div>

        <div className="h-[1px] w-[100px] bg-[#FFC120] sm:w-[150px] lg:w-[200px]" />
      </div>
    </div>
  );
}
