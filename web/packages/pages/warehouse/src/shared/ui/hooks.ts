import { useUnit } from "effector-react";

import { $isOnline } from "@shared/state/network";

/** Writes need the network (07 BO-03/BO-04 offline — "faqat ko'rish"; write-offs online only, qaror #54). */
export function useOnline(): boolean {
  return useUnit($isOnline);
}
