import { useContext } from "react";
import { RuntimeContext } from "./RuntimeContext";

export { RuntimeProvider } from "./RuntimeProvider";

export function useRuntimeState() {
  const context = useContext(RuntimeContext);
  if (!context) throw new Error("useRuntimeState must be used inside RuntimeProvider");
  return context;
}
