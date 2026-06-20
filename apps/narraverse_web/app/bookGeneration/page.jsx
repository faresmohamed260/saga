import Image from "next/image";
import bookgen from "@/public/book-generation.jpeg";
import Title from "./title";
import YourBook from "./yourBook";
import GeneratedBook from "./generatedBook";

export default function Services() {
  return (
    <div className="relative min-h-screen">
      <div>
        <Image
          src={bookgen}
          alt="background"
          fill
          priority
          className="object-cover"
        />
      </div>
      <Title />
      <YourBook />
      <GeneratedBook />
    </div>
  );
}
