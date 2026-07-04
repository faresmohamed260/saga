import { NavItem } from "./NavItem";

export function ShellNav({ items }) {
  return (
    <nav className="sticky top-0 z-20 mt-5 border-b border-white/10 bg-[#070b11]/88 py-3 backdrop-blur-xl">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {items.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </div>
    </nav>
  );
}
