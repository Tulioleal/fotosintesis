import { Suspense } from "react";
import { RemindersManager } from "@/components/reminders/RemindersManager";

export default function RemindersPage() {
  return (
    <Suspense fallback={<p>Cargando recordatorios...</p>}>
      <RemindersManager />
    </Suspense>
  );
}
