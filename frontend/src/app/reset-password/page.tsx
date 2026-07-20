import Link from "next/link";
import { AuthLayout } from "@/components/auth-layout";
import { SimpleAuthForm } from "@/components/simple-auth-form";
export default function Page() {
  return (
    <AuthLayout
      title="Choose a new password"
      description="Use at least eight characters and avoid a password used elsewhere."
      footer={<Link href="/login">Return to sign in</Link>}
    >
      <SimpleAuthForm kind="reset" />
    </AuthLayout>
  );
}
