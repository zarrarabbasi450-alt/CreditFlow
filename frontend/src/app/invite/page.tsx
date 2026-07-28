"use client";
import { Suspense } from "react";
import Link from "next/link";
import { AuthLayout } from "@/components/auth-layout";
import { InviteAccept } from "@/features/auth/invite-accept";
export default function InvitePage() {
  return (
    <AuthLayout
      title="Join your team's workspace"
      description="Accept your invitation to start collaborating on CreditFlow."
      footer={<Link href="/login">Return to sign in</Link>}
    >
      <Suspense fallback={<div className="form-skeleton" />}>
        <InviteAccept />
      </Suspense>
    </AuthLayout>
  );
}
