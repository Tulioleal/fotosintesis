## 1. Project Foundation

- [ ] 1.1 Create frontend and backend project structure according to the technical architecture spec
- [ ] 1.2 Configure TypeScript, React, Next.js, SCSS Modules, TanStack Query and Zustand
- [ ] 1.3 Configure FastAPI, Uvicorn, application settings and environment loading
- [ ] 1.4 Add PostgreSQL + pgvector schema migration baseline
- [ ] 1.5 Add object storage abstraction for user images and temporary identification assets
- [ ] 1.6 Add Docker Compose for frontend, backend, postgres and optional local object storage
- [ ] 1.7 Add common DTO/schema contracts for users, plants, garden, reminders, light measurements, conversations and evaluation

## 2. Provider Interfaces And Observability

- [ ] 2.1 Define provider interfaces for text generation, JSON generation, image analysis, embeddings and judge evaluation
- [ ] 2.2 Implement mock providers for model, vision identification, search and embeddings
- [ ] 2.3 Add provider configuration without coupling domain logic to provider SDKs
- [ ] 2.4 Add structured JSON logging for requests, tool runs, provider calls and errors
- [ ] 2.5 Add health check and metrics endpoints
- [ ] 2.6 Add OpenTelemetry hooks or equivalent tracing around chat, RAG, MaaS, GBIF and ingestion flows

## 3. Authentication And Home

- [ ] 3.1 Implement user registration with validation for required fields, email format, password length and duplicate email
- [ ] 3.2 Implement login, session handling and protected route/API access
- [ ] 3.3 Implement password recovery initiation flow
- [ ] 3.4 Build welcome and auth screens with loading, disabled and error states
- [ ] 3.5 Build Home with primary identification CTA, search, medidor de luz, recordatorios, Mi Jardin and assistant access
- [ ] 3.6 Implement Home empty, loading, error and retry states
- [ ] 3.7 Apply Fotosintesis visual identity, bottom navigation and chosen Spanish tone consistently

## 4. Plant Identification And Taxonomy

- [ ] 4.1 Implement image capture/upload UI with camera permission handling and upload fallback
- [ ] 4.2 Implement backend image receipt, validation, metadata persistence and object storage write
- [ ] 4.3 Implement MaaS multimodal candidate identification through the vision provider interface
- [ ] 4.4 Display up to 3 plant candidates with visible traits, qualitative confidence and possible-match copy
- [ ] 4.5 Integrate GBIF Species API for scientific name validation and normalization
- [ ] 4.6 Persist GBIF identifiers, accepted names, synonyms, genus, family and species metadata
- [ ] 4.7 Block definitive profile generation, garden save and reminders until user confirms a validated candidate
- [ ] 4.8 Implement low-confidence, no-plant, blurry-image, MaaS-unavailable and no-GBIF-match sad paths

## 5. Knowledge Base, RAG And Incremental Acquisition

- [ ] 5.1 Implement knowledge document, source, chunk and embedding persistence models
- [ ] 5.2 Configure LlamaIndex with PostgreSQL + pgvector retrieval
- [ ] 5.3 Implement chunking with required metadata for species, topic, source, confidence, review status and dates
- [ ] 5.4 Implement retrieval filters by species, topic, source, confidence, review status and date
- [ ] 5.5 Implement trusted source search constrained to approved domains and validation rules
- [ ] 5.6 Implement structured knowledge document generation with sources, confidence and auto_ingested review status
- [ ] 5.7 Implement embedding creation and re-retrieval after successful ingestion
- [ ] 5.8 Implement degradation when trusted acquisition fails, including partial answer, limitation notice and retry/manual search path

## 6. Plant Profile And Garden

- [ ] 6.1 Implement plant profile generation/retrieval using RAG evidence
- [ ] 6.2 Render profile sections for names, alias, scientific name, description, characteristics, conditions, care, pests, diseases and recommendations
- [ ] 6.3 Implement alias regional fallback by region, country or language without requiring exact GPS
- [ ] 6.4 Show sources, confidence and limitation messages for partial or dynamically acquired information
- [ ] 6.5 Implement profile CTAs for Add to Mi Jardin, Ask assistant, Create reminder and Measure light
- [ ] 6.6 Implement garden save for confirmed plants with optional image and user customization
- [ ] 6.7 Implement Mi Jardin list, search, detail and empty state
- [ ] 6.8 Implement garden plant deletion with explicit confirmation when active reminders exist

## 7. Assistant And Agent

- [ ] 7.1 Implement chat API and frontend conversation UI
- [ ] 7.2 Implement LangGraph nodes for intent classification, user context loading, retrieval, sufficiency evaluation, answer generation, clarification and failure handling
- [ ] 7.3 Add tools for knowledge search, trusted web search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup
- [ ] 7.4 Implement RAG-grounded botanical answers with source-aware uncertainty handling
- [ ] 7.5 Implement ambiguity handling for references to unspecified plants
- [ ] 7.6 Implement out-of-domain response behavior
- [ ] 7.7 Implement prompt-injection resistance checks and tool-use restrictions
- [ ] 7.8 Implement assistant-triggered reminder creation with confirmation when data is missing
- [ ] 7.9 Implement tool failure handling so the assistant never claims failed actions were completed

## 8. Reminders

- [ ] 8.1 Implement reminder data model with plant, action, date, time, recurrence, status and suggestion justification
- [ ] 8.2 Build manual reminder creation form with validation messages
- [ ] 8.3 Implement reminder list, edit, delete and complete actions
- [ ] 8.4 Implement recurring reminder next-occurrence calculation
- [ ] 8.5 Implement IA-suggested reminders from plant profile, garden context or assistant conversation
- [ ] 8.6 Request notification permissions and preserve reminders when permissions are rejected

## 9. Light Meter

- [ ] 9.1 Implement AmbientLightSensor detection, permission request and lux reading when supported
- [ ] 9.2 Implement camera luminance fallback with approximate-measurement copy
- [ ] 9.3 Implement manual light registration fallback
- [ ] 9.4 Classify light as baja, media, alta or directa with reliability metadata
- [ ] 9.5 Detect unreliable camera measurements such as covered or overexposed image
- [ ] 9.6 Persist light measurements and optionally associate them to plants in Mi Jardin

## 10. Evaluation Pipeline

- [ ] 10.1 Create initial evaluation dataset format and seed 50 cases distributed by target flows
- [ ] 10.2 Implement evaluation runner for assistant_rag, plant_profile_generation, revive_plant, incremental_knowledge, reminders_agent, light_measurement_context and plant_identification_maas
- [ ] 10.3 Calculate retrieval_recall@5 and precision@5
- [ ] 10.4 Calculate BERTScore and ROUGE-L for applicable text outputs
- [ ] 10.5 Implement LLM-as-a-judge rubric for grounding, botanical correctness, usefulness, clarity, safety, uncertainty handling and tool use
- [ ] 10.6 Calculate tool_success_rate, unnecessary_web_search_rate and failed_action_claim_rate
- [ ] 10.7 Calculate visual identification metrics including top_1_accuracy, top_3_accuracy, taxonomy_validation_rate and low_confidence_detection_rate
- [ ] 10.8 Persist evaluation runs, scores, failures and per-flow summaries
- [ ] 10.9 Generate final evaluation report with protocol, metrics, prompts, results, failures, limitations and conclusions

## 11. Testing And Deployment

- [ ] 11.1 Add backend unit tests for auth, taxonomy validation, providers, RAG filters, ingestion and reminders
- [ ] 11.2 Add backend integration tests for health, metrics, chat, plant identification, garden, reminders, light measurements and evaluation endpoints
- [ ] 11.3 Add frontend component tests for forms, Home, candidate selection, profile, garden, reminders and light meter states
- [ ] 11.4 Add Playwright end-to-end tests for auth, Home navigation, identification to profile, garden save, reminder creation, assistant RAG and light fallback
- [ ] 11.5 Add Kubernetes/GKE manifests or Helm chart for frontend, backend and supporting cloud resources
- [ ] 11.6 Document local setup, required environment variables, mocks, provider configuration, evaluation run and deployment path
