import { Cormorant_Garamond } from "next/font/google";
import Link from "next/link";
import Image from "next/image";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function Box({
  titleL,
  titleR,
  descrition,
  button,
  className,
  href,
  image,
  reverse,
}) {
  return (
    <div
      className={`relative z-10 max-w-5xl mx-auto my-[30px] rounded-2xl overflow-hidden flex items-center
    ${reverse ? "flex-row-reverse" : "flex-row"} ${className ?? ""}`}
      style={{
        border: "1px solid rgba(180, 160, 255, 0.25)",
        boxShadow: "0 0 40px rgba(180, 160, 255, 0.15)",
        background: "rgba(10, 5, 30, 0.6)",
        backdropFilter: "blur(10px)",
      }}
    >
      <div
        className={`flex flex-col pl-[50px] pr-[40px] py-[60px] flex-1 ${reverse ? "items-end text-right" : "items-start text-left"}`}
      >
        <p
          className={`${cormorant.className} text-[70px] font-bold leading-[70px]`}
          style={{
            background:
              "linear-gradient(to bottom, #FFFFFF 0%, #D8B4FE 50%, #C084FC 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            filter: "drop-shadow(0 0 10px rgba(216,180,254,0.8))",
          }}
        >
          {titleL} <br /> {titleR}
        </p>
        <p className="text-white/70 text-[17px] pb-[30px] mt-4 max-w-sm">
          {descrition}
        </p>
        <button
          className="px-[50px] py-3 text-lg rounded-full text-white cursor-pointer"
          style={{
            background:
              "linear-gradient(to right, rgba(93, 56, 167, 0), rgba(102, 102, 102, 0.45))",
            border: "1px solid rgba(180, 160, 255, 0.5)",
            boxShadow:
              "0 0 15px rgba(180, 160, 255, 0.4), 0 0 30px rgba(180, 160, 255, 0.2)",
          }}
        >
          <Link href={href}>{button}</Link> <span className="pl-2">➤</span>
        </button>
      </div>

      {image && (
        <div className="relative w-[65%] flex-shrink-0 aspect-video overflow-hidden">
          <Image
            src={image}
            alt={`${titleL} ${titleR}`}
            fill
            className="object-contain"
            quality={100}
            unoptimized
          />
        </div>
      )}
    </div>
  );
}
