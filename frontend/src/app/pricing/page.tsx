import Link from "next/link";
import { ArrowRight, Check, Sparkles } from "lucide-react";

const plans = [
  {
    name: "Free",
    price: "0",
    copy: "For creators exploring a more organized content workflow.",
    features: ["Core content workspace", "1 workspace seat", "Starter usage allowance", "Community support"],
  },
  {
    name: "Pro",
    price: "200",
    copy: "For professionals scaling a consistent content engine.",
    features: [
      "Advanced AI generation",
      "Publishing and scheduling",
      "Higher usage limits",
      "Priority support",
    ],
    featured: true,
  },
  {
    name: "Team",
    price: "600",
    copy: "For collaborative teams managing content production together.",
    features: [
      "Everything in Pro",
      "Team roles and invitations",
      "Shared approval workflows",
      "Team-level usage insights",
    ],
  },
  {
    name: "Enterprise",
    price: "1000",
    copy: "For organizations that need greater scale, control, and guided adoption.",
    features: [
      "Everything in Team",
      "Enterprise usage capacity",
      "Advanced access controls",
      "Dedicated onboarding",
    ],
  },
];

export default function Pricing() {
  return (
    <div className="marketing pricing">
      <nav className="marketing-nav">
        <Link className="logo" href="/">
          <span>
            <Sparkles />
          </span>
          CreditFlow
        </Link>
        <Link className="text-button" href="/login">
          Sign in
        </Link>
      </nav>
      <header>
        <span className="eyebrow">Simple, transparent pricing</span>
        <h1>Invest in output, not overhead.</h1>
        <p>Start free, then upgrade as your content operation and publishing volume grow.</p>
      </header>
      <div className="price-grid">
        {plans.map((plan) => (
          <article className={plan.featured ? "featured" : ""} key={plan.name}>
            {plan.featured && <i>Most popular</i>}
            <h2>{plan.name}</h2>
            <p>{plan.copy}</p>
            <strong>
              ${plan.price}
              <small> / month</small>
            </strong>
            <Link className={plan.featured ? "primary-button" : "secondary-button"} href="/signup">
              Choose {plan.name}
              <ArrowRight />
            </Link>
            <ul>
              {plan.features.map((feature) => (
                <li key={feature}>
                  <Check />
                  {feature}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}
