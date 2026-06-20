import { Suspense } from "react";
import Image from "next/image";
import visual from "@/public/visual.jpeg";
import Title from "./title";
import YourVisual from "./yourVisual";

export default function Visual() {
  return (
    <div className="relative min-h-screen">
      <div>
        <Image
          src={visual}
          alt="audiobook"
          fill
          priority
          className="object-cover"
        />
      </div>
      <Title />
      <Suspense fallback={null}>
        <YourVisual />
      </Suspense>
    </div>
  );
}
