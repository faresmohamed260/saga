import Image from "next/image";
import Link from "next/link";
import logo from "@/public/logo.png";
import { Outfit } from "next/font/google";

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export default function Footer() {
  return (
    <footer className="bg-black/85 backdrop-blur-sm">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-10 sm:px-8 lg:flex-row lg:items-start lg:justify-between lg:px-12">
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Image
              src={logo}
              alt="logo"
              width={65}
              height={63}
              className="h-12 w-auto rotate-[0.5deg]"
            />
            <p className={`${outfit.className} text-xl`}>NARRAVERSE</p>
          </div>
          <p className="max-w-sm text-sm text-white/50 sm:text-base">
            &copy; 2026 Narraverse. All Rights Reserved.
          </p>
        </div>

        <div className={`${outfit.className} grid gap-8 sm:grid-cols-2 lg:grid-cols-3`}>
          <div className="flex flex-col gap-4">
            <p>Services</p>
            <p className="text-white/50">Sequel Generation</p>
            <p className="text-white/50">Image Generation</p>
          </div>

          <div className="flex flex-col gap-4">
            <p>Resources</p>
            <p className="text-white/50">FAQs</p>
            <p className="text-white/50">Help Center</p>
          </div>

          <div className="flex flex-col gap-4">
            <p>Company</p>
            <Link href="/contact" className="text-white/50 hover:text-white">
              Contact Us
            </Link>
            <Link href="/about" className="text-white/50 hover:text-white">
              About Us
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
