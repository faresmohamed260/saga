import Image from "next/image";
import bg from "@/public/conact.jpeg";
import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export default function About() {
  return (
    <div className="relative min-h-screen">
      <div>
        <Image
          src={bg}
          alt="audiobook"
          fill
          priority
          className="object-cover"
        />
      </div>
      <div className="relative z-10 flex  justify-center pt-[150px] pb-[70px]">
        <div className=" rounded-2xl border border-[rgba(180,160,255,0.25)] bg-[#00000080] py-5 px-10  w-[550px] h-fit">
          <p className={`${cormorant.className} text-lg`}>
            We’re building a new kind of storytelling platform, one that
            understands a fictional world before it tries to create within it.
            Our system reads and structures books into a living narrative
            foundation: characters, identities, relationships, timelines, canon
            state, and cause-and-effect across an entire series. That foundation
            can then be stored, reused, and expanded, making it possible to
            generate new story experiences without losing continuity or
            reprocessing the same canon from scratch every time. Today, the
            platform powers deep story analysis, persistent canon memory, sequel
            planning, and continuity-aware generation workflows. It is designed
            for rich multi-book universes where consistency matters and where
            every new story should feel like it truly belongs. We’re also
            building the next generation of features: - mid-canon generation
            that creates stories between existing books - pre-canon generation
            that explores the world before the original timeline - image
            generation for characters, scenes, and visual story concepts Our
            vision is simple: to give creators and readers a system that can
            grow with a story world, preserve what makes it meaningful, and open
            the door to entirely new forms of narrative creation.
          </p>
        </div>
      </div>
    </div>
  );
}
