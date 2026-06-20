import { Cormorant_Garamond } from "next/font/google";
import Image from "next/image";
import p1 from "@/public/p1.png";
import p2 from "@/public/p2.png";
import p3 from "@/public/p3.png";
import arrow from "@/public/arrow.png";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const steps = [
  {
    number: 1,
    image: p1,
    title: "Upload Your Story",
    description: "Share your ideas, plot, or style of your story.",
  },
  {
    number: 2,
    image: p2,
    title: "AI Understands",
    description: "Our AI analyzes your story, characters, and world deeply.",
  },
  {
    number: 3,
    image: p3,
    title: "Generate Magic",
    description: "Get unique stories or stunning visuals in seconds.",
  },
];

export default function Steps() {
  return (
    <div className="relative z-10 flex flex-col items-center pb-[50px] pt-[100px]">
      <div className="flex items-center mb-16">
        <div className="w-[120px] h-[1px] bg-[#FFC120]" />
        <p
          className={`${cormorant.className} px-[30px] text-5xl font-semibold`}
        >
          How It Works
        </p>
        <div className="w-[120px] h-[1px] bg-[#FFC120]" />
      </div>

      {/* Steps Row */}
      <div className="flex items-start justify-center">
        {steps.map((step, index) => (
          <div key={step.number} className="flex items-start">
            {/* Step Card */}
            <div className="flex flex-col items-center text-center w-[170px]">
              {/* Circle Image */}
              <div
                className="w-[160px] h-[160px] rounded-full flex items-center justify-center relative"
                style={{
                  border: "2px solid rgba(180,160,255,0.6)",
                  boxShadow:
                    "0 0 20px rgba(180,160,255,0.5), 0 0 50px rgba(140,100,255,0.3), inset 0 0 20px rgba(0,0,0,0.5)",
                  background: "rgba(0,0,0,0.4)",
                }}
              >
                <Image
                  src={step.image}
                  alt={step.title}
                  width={130}
                  height={130}
                  className="object-contain rounded-full"
                />

                {/* Number Badge */}
                <div
                  className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-7 h-7 rounded-full flex items-center justify-center text-sm text-white"
                  style={{
                    background: "rgba(0,0,0,0.8)",
                    border: "1px solid rgba(180,160,255,0.5)",
                    boxShadow: "0 0 8px rgba(180,160,255,0.4)",
                  }}
                >
                  {step.number}
                </div>
              </div>

              <h3
                className={`${cormorant.className} text-white text-[23px] font-semibold mt-6`}
              >
                {step.title}
              </h3>
              <p className="text-white/60 text-sm leading-relaxed mt-2">
                {step.description}
              </p>
            </div>

            {index < steps.length - 1 && (
              <div className="flex items-center mt-[25px] flex-1 min-w-[80px]">
                <Image
                  src={arrow}
                  alt="arrow"
                  width={200}
                  height={24}
                  className="object-contain"
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
