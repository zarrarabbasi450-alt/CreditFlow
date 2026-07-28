import Link from "next/link";
import { Suspense } from "react";
import { AuthLayout } from "@/components/auth-layout";
import { SignupForm } from "@/features/auth/signup-form";
export default function Signup() {
  return (
    <AuthLayout
      title="Build your content engine"
      description="Create a workspace and invite your team when you are ready."
      footer={
        <>
          Already have an account? <Link href="/login">Sign in</Link>
        </>
      }
    >
      <Suspense fallback={<div className="form-skeleton" />}>
        <SignupForm />
      </Suspense>
    </AuthLayout>
  );
}
