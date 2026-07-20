import Link from "next/link";
import { AuthLayout } from "@/components/auth-layout";
import { SimpleAuthForm } from "@/components/simple-auth-form";
export default function Page() {
  return (
    <AuthLayout
      title="Join Orion Media Group"
      description="Avery invited you to collaborate in CreditFlow."
      footer={
        <>
          Already joined? <Link href="/login">Sign in</Link>
        </>
      }
    >
      <SimpleAuthForm kind="invite" />
    </AuthLayout>
  );
}
