export const candidateEnrichmentQueryKey = (
  candidateId: string,
  scientificName: string,
  language: string,
) => ["candidate-enrichment", candidateId, scientificName, language] as const;
