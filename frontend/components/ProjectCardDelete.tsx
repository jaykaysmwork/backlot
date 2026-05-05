"use client";

import DeleteButton from "./DeleteButton";
import { deleteProject } from "@/lib/api";

export default function ProjectCardDelete({ projectName }: { projectName: string }) {
  return (
    <DeleteButton
      label="project"
      onDelete={() => deleteProject(projectName)}
    />
  );
}
