import { Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="min-h-screen bg-(--vs-bg) text-(--vs-body)">
      <main>
        <Outlet />
      </main>
    </div>
  );
}
