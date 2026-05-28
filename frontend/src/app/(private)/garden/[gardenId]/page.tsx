import { GardenDetail } from "@/components/garden/GardenDetail";
import { AppShell } from "@/components/layout/AppShell";

type GardenDetailPageProps = {
  params: Promise<{ gardenId: string }>;
};

export default async function GardenDetailPage({ params }: Readonly<GardenDetailPageProps>) {
  const { gardenId } = await params;
  return (
    <AppShell>
      <GardenDetail gardenId={gardenId} />
    </AppShell>
  );
}
