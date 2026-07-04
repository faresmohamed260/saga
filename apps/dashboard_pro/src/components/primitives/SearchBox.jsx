import { cx, inputBase } from "./helpers";

export function SearchBox({ value, onChange, placeholder = "Search..." }) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className={cx(inputBase, "rounded-lg px-4 py-3")}
    />
  );
}
