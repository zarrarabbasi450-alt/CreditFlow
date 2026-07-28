"use client";
import Link from "next/link";
import { Suspense } from "react";
import { AuthLayout } from "@/components/auth-layout";
import { VerifyEmail } from "@/features/auth/verify-email";
export default function Page() {
  return (
    <AuthLayout
      title="Verify your email"
      description="One quick confirmation keeps your workspace and notifications secure."
      footer={<Link href="/login">Return to sign in</Link>}
    >
      <Suspense fallback={<div className="form-skeleton" />}>
        <VerifyEmail />
      </Suspense>
    </AuthLayout>
  );
}
