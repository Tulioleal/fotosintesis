export const candidateEnrichmentQueryKey = (
  userId: string,
  candidateId: string,
  scientificName: string,
  language: string,
) =>
  ["candidate-enrichment", userId, candidateId, scientificName, language] as const;
