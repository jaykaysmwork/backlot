"use client";

import DeleteButton from "./DeleteButton";
import { deleteSession } from "@/lib/api";

export default function SessionCardDelete({ sessionId }: { sessionId: string }) {
  return (
    <DeleteButton
      label="session"
      onDelete={() => deleteSession(sessionId)}
    />
  );
}
