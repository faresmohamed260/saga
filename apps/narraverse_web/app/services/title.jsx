import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
export default function Title() {
  return (
    <div className="relative z-10 flex flex-col items-center pt-[150px] pb-[100px] text-center">
      <h1
        className={`${cormorant.className} text-7xl  text-white leading-tight text-center font-bold`}
      >
        Services
      </h1>
    </div>
  );
}
