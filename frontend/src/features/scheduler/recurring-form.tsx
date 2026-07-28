"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { recurringScheduleSchema } from "@/lib/schemas";
import { useToast } from "@/components/toast";
type Values = z.infer<typeof recurringScheduleSchema>;
export function RecurringScheduleForm() {
  const { notify } = useToast();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(recurringScheduleSchema),
    defaultValues: { frequency: "weekly", timezone: "Asia/Karachi" },
  });
  return (
    <form
      className="workflow-form"
      onSubmit={handleSubmit((values) => {
        void values;
        notify("Recurring scheduling is prepared for a future workflow service");
        reset();
      })}
    >
      <div className="field-span">
        <label htmlFor="title">Schedule name</label>
        <input id="title" placeholder="Weekly product insight" {...register("title")} />
        {errors.title && <p role="alert">{errors.title.message}</p>}
      </div>
      <div>
        <label htmlFor="frequency">Frequency</label>
        <select id="frequency" {...register("frequency")}>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div>
        <label htmlFor="timezone">Timezone</label>
        <select id="timezone" {...register("timezone")}>
          <option value="Asia/Karachi">Pakistan (PKT)</option>
          <option value="America/New_York">Eastern Time</option>
          <option value="Europe/London">London</option>
        </select>
      </div>
      <div className="field-span">
        <label htmlFor="startAt">First run</label>
        <input id="startAt" type="datetime-local" {...register("startAt")} />
        {errors.startAt && <p role="alert">{errors.startAt.message}</p>}
      </div>
      <button className="primary-button field-span">Create recurring schedule</button>
    </form>
  );
}
