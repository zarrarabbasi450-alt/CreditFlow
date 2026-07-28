import html
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmailContent:
    subject: str
    html: str
    text: str


def _wrap(title: str, body_lines: list[str], cta: tuple[str, str] | None = None) -> tuple[str, str]:
    text_lines = [title, "", *body_lines]
    html_body = [f"<h2>{html.escape(title)}</h2>"]
    for line in body_lines:
        html_body.append(f"<p>{html.escape(line)}</p>")
    if cta:
        label, url = cta
        text_lines += ["", f"{label}: {url}"]
        html_body.append(f'<p><a href="{html.escape(url)}">{html.escape(label)}</a></p>')
    return "\n".join(html_body), "\n".join(text_lines)


def render_email(event_type: str, payload: dict[str, Any], frontend_url: str) -> EmailContent | None:
    """Returns None for event types that don't produce a customer-facing email
    (e.g. member.joined, which is logged but has no natural recipient message)."""
    base = frontend_url.rstrip("/")

    if event_type == "user.registered":
        link = f"{base}/verify?token={payload['verification_token']}"
        body, text = _wrap(
            "Confirm your email",
            ["One quick click keeps your CreditFlow workspace and notifications secure."],
            ("Verify email", link),
        )
        return EmailContent(subject="Verify your CreditFlow email", html=body, text=text)

    if event_type == "member.invited":
        code = str(payload["invite_token"])
        link = f"{base}/invite?token={code}"
        role = str(payload.get("role", "Member")).title()
        text = "\n".join([
            "You're invited to CreditFlow",
            "",
            f"You've been invited to join a CreditFlow workspace as {role}.",
            "",
            f"Your invite code: {code}",
            "",
            "Paste that code into the \"Accept an invite\" tab on the signup page, or use the link below.",
            "",
            f"Accept invite: {link}",
        ])
        escaped_code = html.escape(code)
        body = "\n".join([
            "<h2>You&#x27;re invited to CreditFlow</h2>",
            f"<p>You&#x27;ve been invited to join a CreditFlow workspace as {html.escape(role)}.</p>",
            "<p>Your invite code:</p>",
            f'<p style="font-family: monospace; font-size: 16px; font-weight: bold;">{escaped_code}</p>',
            "<p>Paste that code into the \"Accept an invite\" tab on the signup page, or use the link "
            "below.</p>",
            f'<p><a href="{html.escape(link)}">Accept invite</a></p>',
        ])
        return EmailContent(subject="You're invited to a CreditFlow workspace", html=body, text=text)

    if event_type == "user.password_reset_requested":
        code = str(payload["reset_code"])
        text = "\n".join([
            "Your CreditFlow password reset code",
            "",
            f"Your one-time code: {code}",
            "",
            "Enter this code on the password reset page to continue. It expires soon and can only be "
            "used once. If you didn't request this, you can safely ignore this email.",
        ])
        escaped_code = html.escape(code)
        body = "\n".join([
            "<h2>Your CreditFlow password reset code</h2>",
            "<p>Your one-time code:</p>",
            f'<p style="font-family: monospace; font-size: 24px; font-weight: bold; '
            f'letter-spacing: 4px;">{escaped_code}</p>',
            "<p>Enter this code on the password reset page to continue. It expires soon and can only "
            "be used once. If you didn&#x27;t request this, you can safely ignore this email.</p>",
        ])
        return EmailContent(subject="Your CreditFlow password reset code", html=body, text=text)

    if event_type == "invoice.paid":
        amount = payload.get("amount", 0)
        currency = str(payload.get("currency", "usd")).upper()
        plan = payload.get("plan", "")
        body, text = _wrap(
            "Payment received",
            [f"We've received your payment of {amount / 100:.2f} {currency} for the {plan} plan. Thanks!"],
            ("View billing", f"{base}/billing"),
        )
        return EmailContent(subject="Your CreditFlow payment receipt", html=body, text=text)

    if event_type == "payment.failed":
        grace = payload.get("grace_period_ends_at", "")
        body, text = _wrap(
            "Payment failed",
            [
                "We couldn't process your latest payment.",
                f"Please update your billing details before {grace} to avoid interruption.",
            ],
            ("Update billing", f"{base}/billing"),
        )
        return EmailContent(subject="Action needed: CreditFlow payment failed", html=body, text=text)

    if event_type == "post.published":
        url = payload.get("linkedin_post_url")
        cta = ("View post", str(url)) if url else None
        body, text = _wrap(
            "Your LinkedIn post is live", ["Your scheduled content was published successfully."], cta
        )
        return EmailContent(subject="Your LinkedIn post was published", html=body, text=text)

    if event_type == "post.failed":
        reason = payload.get("reason", "Unknown error")
        body, text = _wrap(
            "A scheduled post failed",
            [f"We couldn't publish your content to LinkedIn: {reason}"],
            ("Review publishing", f"{base}/publishing/history"),
        )
        return EmailContent(subject="Action needed: LinkedIn publish failed", html=body, text=text)

    if event_type == "usage.threshold_reached":
        percentage = payload.get("threshold_percentage", 0)
        period = payload.get("period", "")
        body, text = _wrap(
            f"You've used {percentage}% of your token quota",
            [f"Your account has reached {percentage}% of its monthly token quota for {period}."],
            ("View usage", f"{base}/usage"),
        )
        subject = f"CreditFlow usage alert: {percentage}% of quota used"
        return EmailContent(subject=subject, html=body, text=text)

    return None


def render_slack_alert(event_type: str, payload: dict[str, Any]) -> str | None:
    if event_type == "payment.failed":
        return f":warning: Payment failed for account `{payload.get('account_id')}`."
    if event_type == "post.failed":
        return (
            f":warning: LinkedIn post failed for account `{payload.get('account_id')}`: "
            f"{payload.get('reason')}"
        )
    if event_type == "usage.threshold_reached":
        return (
            f":bar_chart: Account `{payload.get('account_id')}` reached "
            f"{payload.get('threshold_percentage')}% of its token quota."
        )
    return None
