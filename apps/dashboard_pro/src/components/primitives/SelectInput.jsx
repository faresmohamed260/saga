import { cx, inputBase } from "./helpers";

export function SelectInput({ className = "", children, ...props }) {
  return (
    <select className={cx(inputBase, "cursor-pointer", className)} {...props}>
      {children}
    </select>
  );
}
