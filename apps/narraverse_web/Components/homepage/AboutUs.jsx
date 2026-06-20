import { Krona_One, Roboto } from "next/font/google";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faLocationArrow } from "@fortawesome/free-solid-svg-icons";
import Image from "next/image";
import lens from "@/public/lens.png";
import Link from "next/link";

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["100", "300", "400", "500", "700", "900"],
});

const krona = Krona_One({
  subsets: ["latin"],
  weight: "400",
});

export default function AboutUs() {
  return (
    <section className="mx-auto flex w-full max-w-7xl flex-col-reverse items-center gap-10 px-6 pb-20 pt-12 sm:px-8 lg:flex-row lg:items-start lg:gap-16 lg:px-12">
      <div className="flex-1 text-center lg:text-left">
        <div className="mb-8">
          <p className={`${krona.className} text-3xl sm:text-4xl`}>About Us</p>
          <p className={`${roboto.className} mt-2 text-[#FFC120]`}>
            We are story lovers just like you.
          </p>
        </div>

        <div
          className={`${roboto.className} mx-auto max-w-2xl text-base leading-7 text-white/80 sm:text-lg lg:mx-0`}
        >
          <p>
            Narraverse is an AI-powered platform that brings fictional worlds to
            life, analyzing your books to map characters, relationships,
            timelines, and events, then using that foundation to generate
            continuity-aware sequels, story expansions, visuals, and audio, all
            true to the original canon.
          </p>
        </div>

        <div className="mt-8">
          <Link
            href="/about"
            className={`${roboto.className} inline-flex items-center gap-4 rounded-full border border-[#FFC120] px-5 py-3 text-base text-white transition-colors hover:bg-white/10 sm:text-lg`}
          >
            <span>Learn More About Us</span>
            <FontAwesomeIcon
              icon={faLocationArrow}
              className="h-5 w-5 rotate-45 sm:h-6 sm:w-6"
            />
          </Link>
        </div>
      </div>

      <div className="flex w-full max-w-sm flex-1 justify-center lg:max-w-md lg:justify-end">
        <div className="relative w-full max-w-[260px] sm:max-w-[320px]">
          <Image src={lens} alt="lens" className="h-auto w-full" />
        </div>
      </div>
    </section>
  );
}
