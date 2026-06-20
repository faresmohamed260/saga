import Image from "next/image";
import { Cormorant_Garamond } from "next/font/google";
import star from "@/public/star.png";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function Header() {
  return (
    <section className="relative min-h-screen">
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 pb-16 pt-40 text-center sm:px-8 md:pt-40">
        <h1
          className={`${cormorant.className} max-w-[11ch] text-4xl font-bold leading-[1.1] text-white sm:max-w-4xl sm:text-6xl lg:text-7xl`}
          style={{
            textShadow: `
              0 0 15px rgba(255, 255, 255, 0.6),
              0 0 40px rgba(200, 150, 255, 0.35),
              0 0 80px rgba(180, 100, 255, 0.15)
            `,
          }}
        >
          Your Story <br />
          Isn&apos;t{" "}
          <span
            style={{
              color: "#f0a500",
              textShadow: "0 0 30px rgba(240, 165, 0, 0.8)",
            }}
          >
            Over
          </span>{" "}
          Yet.
        </h1>

        <div className="my-6 flex items-center">
          <div className="h-px w-16 bg-[#FFC120] sm:w-24 md:w-32" />
          <div className="mx-[-10px] flex h-16 w-16 items-center justify-center pb-3 sm:mx-[-16px] sm:h-24 sm:w-24 sm:pb-5">
            <Image src={star} alt="star" className="h-auto w-full" />
          </div>
          <div className="h-px w-16 bg-[#FFC120] sm:w-24 md:w-32" />
        </div>

        <p className="max-w-[22rem] text-sm leading-7 text-white/70 sm:max-w-xl sm:text-lg">
          We help storytellers, dreamers, and creators bring their ideas to life
          and share them with the world
        </p>

        <button
          className="mt-8 cursor-pointer rounded-full px-8 py-3 text-base font-semibold text-white sm:px-10 sm:text-lg"
          style={{
            background: "linear-gradient(to right, #FF3A93, #FFC120)",
            boxShadow: `
              0 6px 12px rgba(255, 255, 255, 0.3),
              -6px 0 12px rgba(255, 255, 255, 0.15),
              6px 0 12px rgba(255, 255, 255, 0.15),
              0 10px 25px rgba(255, 255, 255, 0.1)
            `,
          }}
        >
          Get Started!
        </button>
      </div>
    </section>
  );
}
