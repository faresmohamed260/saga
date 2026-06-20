import { Krona_One, Roboto } from "next/font/google";
import book from "@/public/book.png";
import stars from "@/public/stars.png";
import mic from "@/public/mic.png";
import war from "@/public/war.jpeg";
import Image from "next/image";

const krona = Krona_One({
  subsets: ["latin"],
  weight: "400",
});

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
});

const cards = [
  {
    image: book,
    title: "Make Your Book",
    description: "Continue the story that left everyone wanting more.",
  },
  {
    image: war,
    title: "Image Generation",
    description: "Cinematic visuals that bring your favorite story to life.",
  },
  {
    image: mic,
    title: "Voice Your Story",
    description: "Turn your words into lifelike audio.",
  },
];

export default function Book() {
  return (
    <section className="mx-auto w-full max-w-7xl px-6 pb-20 text-center sm:px-8 lg:px-12">
      <p
        className={`${krona.className} text-3xl sm:text-4xl`}
        style={{
          textShadow: `
              0 0 15px rgba(255, 255, 255, 0.6),
              0 0 40px rgba(200, 150, 255, 0.35),
              0 0 80px rgba(180, 100, 255, 0.15)
            `,
        }}
      >
        Your Story. Our <span className="text-[#FFC120]">Superpowers</span>.
      </p>

      <p
        className={`${roboto.className} mt-3 text-base sm:text-lg`}
        style={{
          background:
            "linear-gradient(to right, #D59BFF, rgba(255, 193, 32, 0.69))",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}
      >
        Here&apos;s What We Do
      </p>

      <div className="mt-10 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card, i) => (
          <div
            key={i}
            className="mx-auto flex w-full max-w-[360px] flex-col rounded-[24px] border border-white/15 bg-white/8 p-5 text-left backdrop-blur-sm"
          >
            <div className="relative mb-4 aspect-square rounded-[16px] border border-white/20 bg-white/10 p-5">
              <div className="relative h-full w-full">
                <Image
                  src={card.image}
                  alt={card.title}
                  fill
                  style={{ objectFit: "contain" }}
                />
              </div>
            </div>

            <p
              className={`${krona.className} mb-2 text-[1.1rem] font-bold text-white`}
            >
              {card.title}
            </p>
            <p className={`${roboto.className} text-sm leading-6 text-white/70`}>
              {card.description}
            </p>
          </div>
        ))}
      </div>

      <div className="relative mx-auto mt-14 flex max-w-4xl flex-col items-center gap-6 rounded-[24px] border border-white/20 bg-white/12 px-6 py-8 backdrop-blur-md sm:px-8 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col items-center gap-4 text-center lg:items-start lg:text-left">
          <p
            className={`${krona.className} text-xl font-bold leading-tight text-white sm:text-2xl`}
          >
            Every great story begins <br /> with a single step.
          </p>
          <Image src={stars} alt="stars" className="h-8 w-8" />
        </div>

        <button
          className="whitespace-nowrap rounded-full bg-gradient-to-r from-[rgba(255,58,147,0.75)] to-[rgba(255,193,32,0.75)] px-8 py-3 text-base font-semibold text-white shadow-[0_6px_12px_rgba(255,255,255,0.3),-6px_0_12px_rgba(255,255,255,0.15),6px_0_12px_rgba(255,255,255,0.15),0_10px_25px_rgba(255,255,255,0.1)] sm:px-10 sm:text-lg"
        >
          Start Your Journey!
        </button>
      </div>
    </section>
  );
}
