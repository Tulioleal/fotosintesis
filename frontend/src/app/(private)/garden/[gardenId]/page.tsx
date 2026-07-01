import { GardenDetail } from "@/components/garden/GardenDetail";

type GardenDetailPageProps = {
  params: Promise<{ gardenId: string }>;
};

export default async function GardenDetailPage({ params }: Readonly<GardenDetailPageProps>) {
  const { gardenId } = await params;
  return <GardenDetail gardenId={gardenId} />;
}
