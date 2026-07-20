import { z } from "zod";
export const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
export const recurringScheduleSchema = z.object({
  title: z.string().min(3, "Title must be at least 3 characters"),
  frequency: z.enum(["daily", "weekly", "monthly", "custom"]),
  timezone: z.string().min(1, "Select a timezone"),
  startAt: z.string().min(1, "Select a start date and time"),
});
export const linkedinImageSchema = z.object({
  caption: z.string().min(10, "Caption must be at least 10 characters").max(3000),
  image: z
    .custom<File>((v) => v instanceof File, "Select an image")
    .refine(
      (f) => !f || ["image/jpeg", "image/png", "image/webp"].includes(f.type),
      "Use a JPG, PNG, or WebP image",
    )
    .refine((f) => !f || f.size <= 5 * 1024 * 1024, "Image must be 5 MB or smaller"),
});
