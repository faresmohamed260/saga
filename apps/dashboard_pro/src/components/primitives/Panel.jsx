import { cx } from "./helpers";
import { SectionHeading } from "./SectionHeading";
import { Surface } from "./Surface";

export function Panel({ title, subtitle, action, children, className = "" }) {
  return (
    <Surface as="section" className={cx("p-5", className)}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <SectionHeading title={title} subtitle={subtitle} />
        {action}
      </div>
      {children}
    </Surface>
  );
}
