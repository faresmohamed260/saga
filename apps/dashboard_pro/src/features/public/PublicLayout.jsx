import { Outlet } from "react-router-dom";

export function PublicLayout() {
  return (
    <div className="min-h-screen text-slate-100">
      <Outlet />
    </div>
  );
}
