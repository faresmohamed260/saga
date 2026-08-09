import { cx, inputBase } from "./helpers";

export function TextArea({ className = "", ...props }) {
  return <textarea className={cx(inputBase, "min-h-36 resize-y", className)} {...props} />;
}
