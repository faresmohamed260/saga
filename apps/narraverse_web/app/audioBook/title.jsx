import { Cormorant_Garamond } from "next/font/google";
import star from "@/public/star.png";
import Image from "next/image";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
export default function Title() {
  return (
    <div className="relative z-10 flex flex-col items-center justify-center pt-[100px] text-center px-8">
      <h1
        className={`${cormorant.className} text-6xl  text-white leading-tight text-center`}
      >
        Create Your{" "}
        <span className="bg-gradient-to-r from-[rgba(255,193,32,0.69)] via-[#FFC120] to-[rgba(183,137,17,0.69)] bg-clip-text text-transparent">
          Audio Book
        </span>
      </h1>

      <div className="flex items-center ">
        <div className="w-[200px] h-[1px] bg-[#FFC120]" />

        <div className="w-[120px] h-[118px] mx-[-20px] pb-6 flex items-center justify-center">
          <Image src={star} alt="star" />
        </div>

        <div className="w-[200px] h-[1px] bg-[#FFC120]" />
      </div>
    </div>
  );
}
