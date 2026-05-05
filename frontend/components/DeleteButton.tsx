"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function DeleteButton({
  label,
  onDelete,
  redirectTo,
}: {
  label: string;
  onDelete: () => Promise<void>;
  redirectTo?: string;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();

    if (!confirming) {
      setConfirming(true);
      return;
    }

    setDeleting(true);
    try {
      await onDelete();
      if (redirectTo) {
        router.push(redirectTo);
      } else {
        router.refresh();
      }
    } catch {
      setDeleting(false);
      setConfirming(false);
    }
  }

  function handleCancel(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setConfirming(false);
  }

  if (confirming) {
    return (
      <span className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="rounded-md bg-red-600 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-red-500 transition disabled:opacity-50"
        >
          {deleting ? "..." : `Delete ${label}`}
        </button>
        <button
          onClick={handleCancel}
          className="rounded-md bg-[color:var(--bg-2)] border border-[color:var(--border-subtle)] px-2.5 py-1 text-[11px] text-[color:var(--text-3)] hover:text-[color:var(--text-1)] transition"
        >
          Cancel
        </button>
      </span>
    );
  }

  return (
    <button
      onClick={handleDelete}
      title={`Delete ${label}`}
      className="rounded-md p-1.5 text-[color:var(--text-muted)] hover:text-red-400 hover:bg-[color:var(--bg-2)] transition"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 6h18" />
        <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      </svg>
    </button>
  );
}
