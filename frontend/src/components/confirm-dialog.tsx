"use client";
import { AlertTriangle } from "lucide-react";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = true,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onMouseDown={onCancel}>
      <div
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        className="confirm-dialog"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="confirm-dialog-icon" data-danger={danger}>
          <AlertTriangle />
        </div>
        <h3>{title}</h3>
        <p>{description}</p>
        <div className="confirm-dialog-actions">
          <button type="button" className="secondary-button" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? "danger-button" : "primary-button"}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
