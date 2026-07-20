"use client";
import Link from "next/link";
import { Suspense } from "react";
import { AuthLayout } from "@/components/auth-layout";
import { LoginForm } from "@/features/auth/login-form";
export default function LoginPage() {
  return (
    <AuthLayout
      title="Sign in to your workspace"
      description="Continue creating, scheduling, and publishing with your team."
      footer={
        <>
          New to CreditFlow? <Link href="/signup">Create an account</Link>
        </>
      }
    >
      <Suspense fallback={<div className="form-skeleton" />}>
        <LoginForm />
      </Suspense>
      <div className="demo-note">
        <strong>Demo access</strong>
        <code>owner@orionmedia.com</code>
        <code>Password123!</code>
      </div>
    </AuthLayout>
  );
}
