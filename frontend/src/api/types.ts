/**
 * API/SSE type contracts — a 1:1 mirror of the backend Pydantic models.
 *
 * SAME-COMMIT RULE (plans/08 §19 trap): the field names below must not drift
 * from the backend. They are transcribed verbatim from:
 *   - backend/app/models/artifacts.py  (ImageRef, Direction, ConceptPackage, …)
 *   - backend/app/models/views.py       (ProjectSummary, ProjectView, EventOut)
 *   - backend/app/models/events.py      (RunState, EventType, DirectionChange, payloads)
 *   - backend/app/config.py             (health_snapshot)
 * Do NOT rename or invent fields here.
 */

// --------------------------------------------------------------------------- //
// primitives / literal unions (artifacts.py)                                   //
// --------------------------------------------------------------------------- //
export type ImageKind = 'generated' | 'sourced' | 'placeholder';
export type Verdict = 'ship' | 'revise' | 'kill';
export type DirectionStatus = 'draft' | 'promoted' | 'killed' | 'merged_away';
export type Brain = string; // provider label, e.g. 'conceptial' | 'claude_high_temp' | 'mock' | 'glm'

// backend/app/models/artifacts.py :: SourceRef
export interface SourceRef {
  title: string;
  url: string;
  snippet: string;
  query: string | null;
}

// backend/app/models/artifacts.py :: ImageRef
export interface ImageRef {
  kind: ImageKind;
  url: string;
  provider: string;
  license: string;
  // generated-only
  gen_model: string | null;
  gen_prompt: string | null;
  // sourced-only
  source_url: string | null;
  attribution: string | null;
  // descriptive / placeholder label
  caption: string | null;
}

// backend/app/models/artifacts.py :: Annotation
export interface Annotation {
  text: string;
  author: string;
  at: string | null;
}

// backend/app/models/artifacts.py :: Brief
export interface Brief {
  brief: string;
  brand_name: string;
  constraints: string[];
  audience: string;
}

// backend/app/models/artifacts.py :: Strategy
export interface Strategy {
  positioning: string;
  key_message: string;
  pillars: string[];
  rationale: string;
}

// backend/app/models/artifacts.py :: VerbalIdentity
export interface VerbalIdentity {
  names: string[];
  tagline: string;
  tone: string;
  screened: false;
}

// backend/app/models/artifacts.py :: CreativeBrief
export interface CreativeBrief {
  objective: string;
  audience: string;
  key_message: string;
  tone: string;
  mandatories: string[];
}

// backend/app/models/artifacts.py :: Territory
export interface Territory {
  label: string;
  lens: string;
  description: string;
}

// backend/app/models/artifacts.py :: PaletteColor
export interface PaletteColor {
  name: string;
  hex: string;
  role: string;
}

// backend/app/models/artifacts.py :: TypeChoice
export interface TypeChoice {
  role: string;
  family: string;
  fallback: string;
  weights: string[];
}

// backend/app/models/artifacts.py :: ArtDirectionSpec
export interface ArtDirectionSpec {
  mood_descriptors: string[];
  imagery_direction: string;
  layout_notes: string;
  palette: PaletteColor[];
  typography: TypeChoice[];
  moodboard: ImageRef[];
}

// backend/app/models/artifacts.py :: CopyDeck
export interface CopyDeck {
  headline: string;
  subhead: string;
  body: string;
  taglines: string[];
  cta: string;
}

// backend/app/models/artifacts.py :: CritiqueScore
export interface CritiqueScore {
  distinctiveness: number;
  strategic_fit: number;
  memorability: number;
  audience_resonance: number;
  feasibility: number;
  case_against: string;
  verdict: Verdict;
  critic_model: string;
}

// backend/app/models/artifacts.py :: Direction
export interface Direction {
  id: string;
  territory: Territory;
  big_idea: string;
  brain: Brain;
  art_direction: ArtDirectionSpec;
  copy: CopyDeck;
  sketches: ImageRef[];
  critique: CritiqueScore | null;
  critique_stale: boolean;
  divergence_score: number | null;
  status: DirectionStatus;
  annotations: Annotation[];
  // lineage
  parent_id: string | null;
  merged_from: string[];
  lens_tweak: string | null;
}

// backend/app/models/artifacts.py :: ConceptPackage
export interface ConceptPackage {
  direction_id: string;
  territory_label: string;
  strategy: Strategy;
  big_idea: string;
  names: string[];
  sketches: ImageRef[];
  art_direction: ArtDirectionSpec;
  copy: CopyDeck;
  rationale: string;
}

// backend/app/models/artifacts.py :: CostRecord
export interface CostRecord {
  agent: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
}

// backend/app/models/artifacts.py :: DIVERGENCE_FIELDS
export const DIVERGENCE_FIELDS = [
  'big_idea',
  'copy.headline',
  'art_direction.imagery_direction',
] as const;

// backend/app/models/artifacts.py :: EDITABLE_FIELDS
export const EDITABLE_FIELDS = [
  'big_idea',
  'copy.headline',
  'copy.subhead',
  'copy.body',
  'copy.cta',
  'art_direction.imagery_direction',
  'art_direction.layout_notes',
  'art_direction.mood_descriptors',
] as const;

export type EditableField = (typeof EDITABLE_FIELDS)[number];

// --------------------------------------------------------------------------- //
// view models (views.py)                                                       //
// --------------------------------------------------------------------------- //
// backend/app/models/views.py :: ProjectSummary
export interface ProjectSummary {
  id: string;
  state: string; // a RunState value
  brief_excerpt: string;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// backend/app/models/views.py :: EventOut
export interface EventOut {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  at: string | null;
}

// backend/app/models/views.py :: ProjectView (extends ProjectSummary)
export interface ProjectView extends ProjectSummary {
  brief: Brief | null;
  strategy: Strategy | null;
  verbal_identity: VerbalIdentity | null;
  creative_brief: CreativeBrief | null;
  territories: Territory[];
  directions: Direction[];
  divergence: DivergenceReport | null;
  packages: ConceptPackage[];
  interrupt: InterruptPayload | null;
}

// divergence report (backend/app/services/divergence.py -> {min, mean, warning})
export interface DivergenceReport {
  min: number | null;
  mean: number | null;
  warning: boolean;
}

// interrupt payloads surfaced by the gates (curation/strategy):
//   strategy_gate -> {gate:"strategy", strategy}
//   curation_gate -> {gate:"curation", directions:[summary], divergence}
export interface InterruptPayload {
  gate: string; // "strategy" | "curation" | "clarify"
  strategy?: Strategy | null;
  directions?: DirectionSummary[];
  divergence?: DivergenceReport | null;
  payload?: Record<string, unknown>;
  [k: string]: unknown;
}

// curation-gate direction summary (backend/app/graph/curation.py :: _summary)
export interface DirectionSummary {
  id: string;
  big_idea: string;
  headline: string;
  brain: Brain;
  status: DirectionStatus;
  critique_stale: boolean;
  divergence_score: number | null;
  critique: CritiqueScore | null;
  annotations: Annotation[];
  parent_id: string | null;
  merged_from: string[];
}

// --------------------------------------------------------------------------- //
// event vocabulary (events.py)                                                 //
// --------------------------------------------------------------------------- //
// backend/app/models/events.py :: RunState
export type RunState =
  | 'intake'
  | 'interrogating'
  | 'researching'
  | 'strategizing'
  | 'awaiting_strategy_approval'
  | 'naming'
  | 'briefing'
  | 'seeding'
  | 'exploring'
  | 'diverging'
  | 'awaiting_curation'
  | 'refining'
  | 'packaging'
  | 'done'
  | 'cancelled'
  | 'error';

// backend/app/models/events.py :: EventType
export type EventType =
  | 'run_created'
  | 'run_state_changed'
  | 'agent_started'
  | 'agent_completed'
  | 'agent_failed'
  | 'agent_token'
  | 'artifact_written'
  | 'direction_created'
  | 'direction_updated'
  | 'divergence_computed'
  | 'gate_reached'
  | 'gate_resolved'
  | 'cost_recorded'
  | 'run_cancelled';

// backend/app/models/events.py :: DirectionChange (the `change` discriminator)
export type DirectionChange =
  | 'edit'
  | 'regenerate_field'
  | 'regenerate_sketch'
  | 'regenerate_sketches'
  | 'regenerate_moodboard_item'
  | 'recritique';

// One SSE frame, parsed. `type` is an EventType; `data` is the parsed payload.
export interface SseEvent {
  seq: number;
  type: EventType | string;
  data: Record<string, unknown>;
}

// ----- payload shapes (events.py TypedDicts) ------------------------------- //
export interface RunCreatedPayload {
  project_id?: string;
  brief_excerpt?: string;
}
export interface RunStateChangedPayload {
  from_state?: string;
  to_state?: string;
}
export interface GatePayload {
  gate?: string; // "strategy" | "curation"
  payload?: Record<string, unknown>;
}
export interface DirectionCreatedPayload {
  direction_id?: string;
  brain?: string;
}
export interface DirectionUpdatedPayload {
  direction_id?: string;
  change?: string; // one of DirectionChange
}
export interface DivergenceComputedPayload {
  min?: number;
  mean?: number;
  warning?: boolean;
}
export interface AgentEventPayload {
  agent?: string;
  error?: string | null;
}
export interface AgentTokenPayload {
  agent?: string;
  token?: string;
  text?: string;
}
export interface CostRecordedPayload {
  agent?: string;
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
}

// --------------------------------------------------------------------------- //
// health snapshot (config.py :: health_snapshot)                               //
// --------------------------------------------------------------------------- //
export interface HealthSnapshot {
  status: string;
  providers: {
    claude: string;
    conceptial: string;
    search: string;
    embeddings: string;
  };
  image_gen: { enabled: boolean; provider: string | null };
  image_source: { enabled: boolean; provider: string | null };
  tracing: boolean;
}

// --------------------------------------------------------------------------- //
// request bodies (routes_*.py)                                                 //
// --------------------------------------------------------------------------- //
export interface CreateProjectBody {
  brief: string;
  brand_name?: string;
  constraints?: string[];
  audience?: string;
}

export interface GateStrategyBody {
  action: 'approve' | 'reject';
  edits?: Record<string, unknown>;
  notes?: string;
}

export interface EditBody {
  field: EditableField;
  value: unknown;
}

export interface MergeBody {
  direction_ids: string[];
  field_choices: Record<string, unknown>;
}
