import LeftBox from "./boxes/leftBox";
import MiddleBox from "./boxes/middleBox";
import RightBox from "./boxes/rightBox";

export default function YourBook() {
  return (
    <div className="relative z-10 flex justify-end gap-5 pb-[100px] pr-16">
      <LeftBox />
      <MiddleBox />
      <RightBox />
    </div>
  );
}
