import Link from "next/link";
import { AuthLayout } from "@/components/auth-layout";
import { ForgotPasswordFlow } from "@/features/auth/forgot-password-flow";
export default function Page() {
  return (
    <AuthLayout
      title="Reset your password"
      description="We'll email you a one-time code to confirm it's really you."
      footer={<Link href="/login">Return to sign in</Link>}
    >
      <ForgotPasswordFlow />
    </AuthLayout>
  );
}
