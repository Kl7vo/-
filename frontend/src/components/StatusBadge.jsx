import { STATUS_META } from "@/lib/rsvp";

export const StatusBadge = ({ status, testId }) => {
  const meta = STATUS_META[status] || { label: status, cls: "border-neutral-700 text-neutral-400" };
  return (
    <span data-testid={testId} data-status={status}
      className={`inline-flex items-center whitespace-nowrap border px-2 py-0.5 text-[11px] font-bold tracking-wide rounded-sm ${meta.cls}`}>
      {meta.label}
    </span>
  );
};
