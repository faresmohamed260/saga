import Image from "next/image";
import homepage from "@/public/homepage.jpeg";

import Header from "./Header";
import Aboutus from "./AboutUs";
import Book from "./Book";

export default function HomePage() {
  return (
    <div className="relative min-h-screen">
      <Image
        src={homepage}
        alt="background"
        fill
        priority
        className="object-cover"
      />

      <div className="relative z-10">
        <Header />
        <Aboutus />
        <Book />
      </div>
    </div>
  );
}
