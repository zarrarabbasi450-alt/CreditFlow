import Link from "next/link";
import { ArrowLeft, Quote, Sparkles } from "lucide-react";
export function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <main className="auth-page">
      <section className="auth-art">
        <Link className="logo" href="/">
          <span>
            <Sparkles />
          </span>
          CreditFlow
        </Link>
        <div>
          <Quote />
          <blockquote>
            CreditFlow gave our small team the operating discipline of a full content studio—without slowing
            down the creative work.
          </blockquote>
          <p>
            Avery Moore <span>· VP, Content Strategy</span>
          </p>
        </div>
        <small>Content operations, beautifully composed.</small>
      </section>
      <section className="auth-panel">
        <Link className="back-link" href="/">
          <ArrowLeft />
          Back to home
        </Link>
        <div className="auth-box">
          <span className="eyebrow">Welcome to CreditFlow</span>
          <h1>{title}</h1>
          <p>{description}</p>
          {children}
          <footer>{footer}</footer>
        </div>
      </section>
    </main>
  );
}
