"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ImagePlus } from "lucide-react";
import { linkedinImageSchema } from "@/lib/schemas";
import { useToast } from "@/components/toast";
import { usePublishToLinkedIn } from "@/hooks/usePublishing";
type Values = z.infer<typeof linkedinImageSchema>;
export function LinkedInImageForm() {
  const { notify } = useToast();
  const publish = usePublishToLinkedIn();
  const {
    register,
    setValue,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(linkedinImageSchema) });
  const image = register("image");
  return (
    <form
      className="workflow-form"
      onSubmit={handleSubmit(async (values) => {
        await publish.mutateAsync({
          caption: values.caption,
          imageUrl: undefined,
        });
        notify("LinkedIn image post queued");
      })}
    >
      <div className="field-span">
        <label htmlFor="caption">Post caption</label>
        <textarea
          id="caption"
          rows={7}
          placeholder="Share the insight behind this image…"
          {...register("caption")}
        />
        {errors.caption && <p role="alert">{errors.caption.message}</p>}
      </div>
      <div className="upload field-span">
        <ImagePlus />
        <label htmlFor="image">Choose a JPG, PNG, or WebP image</label>
        <small>Maximum file size 5 MB</small>
        <input
          id="image"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          name={image.name}
          ref={image.ref}
          onBlur={image.onBlur}
          onChange={(e) => setValue("image", e.target.files?.[0] as File, { shouldValidate: true })}
        />
        {errors.image && <p role="alert">{errors.image.message}</p>}
      </div>
      <button className="primary-button field-span">Publish to LinkedIn</button>
    </form>
  );
}
