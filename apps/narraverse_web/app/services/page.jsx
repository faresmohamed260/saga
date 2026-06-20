import Image from "next/image";
import visual from "@/public/services2.jpeg";
import Steps from "./steps";
import Title from "./title";
import Box from "./box";
import p1 from "@/public/p1111.jpeg";
import p2 from "@/public/p222.jpeg";
import p3 from "@/public/p333.jpeg";

export default function Services() {
  return (
    <div className="relative min-h-screen">
      <div className="absolute inset-0 z-0">
        <Image
          src={visual}
          alt="audiobook"
          fill
          priority
          className="object-cover"
        />
      </div>

      <div className="relative z-10">
        <Title />

        <Box
          titleL="Book"
          titleR="Generation"
          descrition="Continue your story beyond imagination. Our AI crafts engaging books that stay true to your characters, world, and plot while opening doors to new adventures."
          button="Try Book Generator"
          reverse={false}
          href="/bookGeneration"
          image={p1}
        />

        <Box
          titleL="Image/Scene"
          titleR="Generation"
          descrition="Turn your words into stunning visuals. Generate high-quality, cinematic scenes and character images that bring your story to life instantly."
          button="Try Image Generator"
          reverse={true}
          href="/visual?from=services"
          image={p2}
        />

        <Box
          titleL="Audio"
          titleR="Generation"
          descrition="Bring your story to life through AI narration. Convert every chapter into high-quality audio with natural AI voices, cinematic delivery, and seamless chapter-by-chapter generation."
          button="Try Audio Generator"
          reverse={false}
          href="/audioBook?from=services"
          image={p3}
        />

        <Steps />

        <div className="pb-[70px]">
          <button
            className="mx-auto block cursor-pointer rounded-full px-[50px] py-2 text-white"
            style={{
              background:
                "linear-gradient(to right, rgba(93, 56, 167, 0), rgba(102, 102, 102, 0.45))",
              border: "1px solid rgba(180, 160, 255, 0.5)",
              boxShadow:
                "0 0 15px rgba(180, 160, 255, 0.4), 0 0 30px rgba(180, 160, 255, 0.2)",
            }}
          >
            Start Creating Your Story <span className="pl-2">{"<3"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
