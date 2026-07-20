import Link from "next/link";
import { AuthLayout } from "@/components/auth-layout";
import { SimpleAuthForm } from "@/components/simple-auth-form";
export default function Page() {
  return (
    <AuthLayout
      title="Reset your password"
      description="We will send a secure link to the email connected to your workspace."
      footer={<Link href="/login">Return to sign in</Link>}
    >
      <SimpleAuthForm kind="forgot" />
    </AuthLayout>
  );
}
