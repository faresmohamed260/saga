import { cx, inputBase } from "./helpers";

export function TextInput({ className = "", ...props }) {
  return <input className={cx(inputBase, className)} {...props} />;
}
