import { redirect } from "next/navigation";
// The reset flow is now a single OTP wizard (request code -> verify -> set
// password) that never needs a link/token in the URL, so it all lives at
// /forgot-password. This route stays as a redirect in case anything still
// links here.
export default function Page() {
  redirect("/forgot-password");
}
