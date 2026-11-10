"use server";

import { revalidatePath } from "next/cache";
import { requireReviewer } from "@/lib/auth";
import { approveFact, correctFact, rejectFact } from "@/lib/mutations";
import type { FactType } from "@/lib/types";

export async function approveFactAction(slug: string, factType: FactType, id: string) {
  await requireReviewer();
  await approveFact(factType, id);
  revalidatePath(`/deals/${slug}`);
}

export async function rejectFactAction(slug: string, factType: FactType, id: string, note: string) {
  await requireReviewer();
  await rejectFact(factType, id, note);
  revalidatePath(`/deals/${slug}`);
}

export async function correctFactAction(
  slug: string,
  factType: FactType,
  id: string,
  fields: Record<string, unknown>,
  note: string | null
) {
  await requireReviewer();
  await correctFact(factType, id, fields, note);
  revalidatePath(`/deals/${slug}`);
}
