import Link from "next/link";
import { ArrowRight, BarChart3, CalendarCheck, Check, Layers3, Sparkles, WandSparkles } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="marketing">
      <nav className="marketing-nav">
        <Link className="logo" href="/">
          <span>
            <Sparkles />
          </span>
          CreditFlow
        </Link>
        <div>
          <a href="#platform">Platform</a>
          <Link href="/pricing">Pricing</Link>
          <a href="#security">Security</a>
        </div>
        <div>
          <Link className="text-button" href="/login">
            Sign in
          </Link>
          <Link className="primary-button" href="/signup">
            Start free <ArrowRight />
          </Link>
        </div>
      </nav>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <Sparkles />
              The content operating system for ambitious teams
            </div>
            <h1>
              Turn ideas into <em>momentum.</em>
            </h1>
            <p>
              Generate, organize, schedule, and publish exceptional content—then understand exactly what it
              costs and what it achieves.
            </p>
            <div className="hero-actions">
              <Link className="primary-button" href="/signup">
                Build your content engine <ArrowRight />
              </Link>
              <Link className="secondary-button" href="/login">
                Explore the workspace
              </Link>
            </div>
            <small>
              <Check />
              14-day trial <Check />
              No credit card <Check />
              Cancel anytime
            </small>
          </div>
          <div className="hero-orbit" aria-label="CreditFlow workflow illustration">
            <div className="orbit-card main">
              <span>
                <WandSparkles />
              </span>
              <strong>AI campaign generated</strong>
              <small>4 assets · Brand voice 96%</small>
              <i>Ready for review</i>
            </div>
            <div className="orbit-card one">
              <CalendarCheck />
              <strong>11 posts</strong>
              <small>scheduled</small>
            </div>
            <div className="orbit-card two">
              <BarChart3 />
              <strong>−22%</strong>
              <small>cost per output</small>
            </div>
            <div className="glow" />
          </div>
        </section>
        <section className="trust">
          <span>TRUSTED BY MODERN CONTENT TEAMS</span>
          <div>
            <strong>Northstar</strong>
            <strong>ORBITAL</strong>
            <strong>Vertex Labs</strong>
            <strong>monogram</strong>
            <strong>WAYFIND</strong>
          </div>
        </section>
        <section id="platform" className="feature-section">
          <div>
            <span className="eyebrow">
              <Layers3 />
              One connected workspace
            </span>
            <h2>From first thought to published impact.</h2>
          </div>
          <div className="feature-grid">
            {[
              [
                "01",
                "Create with context",
                "Generate on-brand content with model choice, streaming output, and transparent cost.",
              ],
              [
                "02",
                "Operate at scale",
                "Manage approvals, reusable assets, recurring schedules, and multi-user workflows.",
              ],
              [
                "03",
                "Publish with confidence",
                "Connect LinkedIn, ship text and image posts, and track every provider response.",
              ],
              [
                "04",
                "Measure every decision",
                "See token usage, credit movement, model cost, and operational health in one place.",
              ],
            ].map(([n, title, copy]) => (
              <article key={n}>
                <span>{n}</span>
                <h3>{title}</h3>
                <p>{copy}</p>
                <ArrowRight />
              </article>
            ))}
          </div>
        </section>
      </main>
      <footer>
        <Link className="logo" href="/">
          <span>
            <Sparkles />
          </span>
          CreditFlow
        </Link>
        <p>Built for content teams that value clarity, speed, and control.</p>
        <small>© 2026 CreditFlow</small>
      </footer>
    </div>
  );
}
