import Link from "next/link";
import { AuthLayout } from "@/components/auth-layout";
import { SimpleAuthForm } from "@/components/simple-auth-form";
export default function Page() {
  return (
    <AuthLayout
      title="Verify your email"
      description="One quick confirmation keeps your workspace and notifications secure."
      footer={<Link href="/login">Return to sign in</Link>}
    >
      <SimpleAuthForm kind="verify" />
    </AuthLayout>
  );
}
