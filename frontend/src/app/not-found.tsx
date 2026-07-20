import Link from "next/link";
import { Compass } from "lucide-react";
export default function NotFound() {
  return (
    <main className="not-found">
      <Compass />
      <span>404</span>
      <h1>This page drifted off course.</h1>
      <p>The destination may have moved, or your role may not have access to it.</p>
      <Link className="primary-button" href="/dashboard">
        Return to dashboard
      </Link>
    </main>
  );
}
