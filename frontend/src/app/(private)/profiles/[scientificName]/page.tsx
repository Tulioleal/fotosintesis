import { AppShell } from "@/components/layout/AppShell";
import { PlantProfileView } from "@/components/garden/PlantProfileView";

type ProfilePageProps = {
  params: Promise<{ scientificName: string }>;
  searchParams: Promise<{ candidateId?: string }>;
};

export default async function ProfilePage({ params, searchParams }: Readonly<ProfilePageProps>) {
  const { scientificName } = await params;
  const { candidateId } = await searchParams;
  return (
    <AppShell>
      <PlantProfileView scientificName={decodeURIComponent(scientificName)} confirmedCandidateId={candidateId} />
    </AppShell>
  );
}
