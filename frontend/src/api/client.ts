/**
 * Typed REST client over the backend (§13). fetch-based, base "/api". The frontend
 * talks ONLY to this surface + the SSE stream — never to any model/image/search
 * provider directly (§2).
 *
 * Every op returns the updated ProjectView (the curation/gate handlers all do),
 * except create/start/list/health and the export/token downloads. A non-2xx
 * response throws `ApiError` carrying the status (so callers can special-case 409
 * "not in the right state" to keep buttons locked mid-flight).
 */
import type {
  Brief,
  ConceptPackage,
  CreateProjectBody,
  DivergenceReport,
  EditableField,
  GateIdeationBody,
  GateStrategyBody,
  HealthSnapshot,
  IdeationMode,
  ImageKind,
  ProjectSummary,
  ProjectView,
} from './types';

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
  get isConflict(): boolean {
    return this.status === 409;
  }
}

const BASE = '/api';

async function request<T>(
  path: string,
  init?: RequestInit & { rawText?: boolean }
): Promise<T> {
  // Never force JSON content-type on a FormData body — the browser must set the
  // multipart boundary itself (file uploads).
  const isForm = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    headers: init?.body && !isForm ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  });
  if (!res.ok) {
    let body: unknown = undefined;
    let message = `${res.status} ${res.statusText}`;
    try {
      body = await res.json();
      const err = (body as { error?: { message?: string } })?.error;
      if (err?.message) message = err.message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message, body);
  }
  if (init?.rawText) return (await res.text()) as unknown as T;
  // 202/204 may have no body
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  });

const get = <T>(path: string) => request<T>(path, { method: 'GET' });

// --------------------------------------------------------------------------- //
// project lifecycle                                                             //
// --------------------------------------------------------------------------- //
export const api = {
  health: () => get<HealthSnapshot>('/health'),

  createProject: (body: CreateProjectBody) =>
    post<{ id: string; state: string }>('/projects', body),

  // Upload a client RFP PDF; the backend distills a Brief and seeds a project.
  createProjectFromPdf: (file: File, ideationMode: IdeationMode = 'internal') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('ideation_mode', ideationMode);
    return request<{ id: string; state: string; brief: Brief }>('/projects/from-pdf', {
      method: 'POST',
      body: fd,
    });
  },

  listProjects: () => get<ProjectSummary[]>('/projects'),

  getProject: (id: string) => get<ProjectView>(`/projects/${id}`),

  startProject: (id: string) => post<{ status: string }>(`/projects/${id}/start`),

  clarify: (id: string, answers: string[]) =>
    post<ProjectView>(`/projects/${id}/clarify`, { answers }),

  resolveStrategyGate: (id: string, body: GateStrategyBody) =>
    post<ProjectView>(`/projects/${id}/gates/strategy`, body),

  // ---- ideation gate (manual mode): download packet, submit ideas, proceed ----
  resolveIdeationGate: (id: string, body: GateIdeationBody) =>
    post<ProjectView>(`/projects/${id}/gates/ideation`, body),

  ideationPacketUrl: (id: string) => `${BASE}/projects/${id}/ideation-packet.md`,

  // ---- direction ops (all require awaiting_curation; 409 otherwise) ----
  promote: (id: string, did: string) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/promote`),

  kill: (id: string, did: string) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/kill`),

  recritique: (id: string, did: string) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/recritique`),

  annotate: (id: string, did: string, text: string, author = 'human') =>
    post<ProjectView>(`/projects/${id}/directions/${did}/annotate`, { text, author }),

  editField: (id: string, did: string, field: EditableField | string, value: unknown) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/edit`, { field, value }),

  regenerateField: (id: string, did: string, field: EditableField | string) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/regenerate_field`, { field }),

  fork: (id: string, did: string, lens_tweak?: string | null) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/fork`, { lens_tweak: lens_tweak ?? null }),

  regenerateSketch: (id: string, did: string, index: number, prompt?: string | null) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/regenerate_sketch`, {
      index,
      prompt: prompt ?? null,
    }),

  regenerateSketches: (id: string, did: string) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/regenerate_sketches`),

  regenerateMoodboardItem: (
    id: string,
    did: string,
    index: number,
    kind?: ImageKind | null,
    prompt?: string | null
  ) =>
    post<ProjectView>(`/projects/${id}/directions/${did}/regenerate_moodboard_item`, {
      index,
      kind: kind ?? null,
      prompt: prompt ?? null,
    }),

  merge: (id: string, direction_ids: string[], field_choices: Record<string, unknown>) =>
    post<ProjectView>(`/projects/${id}/directions/merge`, { direction_ids, field_choices }),

  finalize: (id: string, refine?: boolean | null) =>
    post<ProjectView>(`/projects/${id}/finalize`, { refine: refine ?? null }),

  // ---- reads ----
  divergence: (id: string) => get<DivergenceReport>(`/projects/${id}/divergence`),
  packages: (id: string) => get<ConceptPackage[]>(`/projects/${id}/packages`),

  // ---- export / tokens (download URLs; also fetchable as text) ----
  exportMarkdownUrl: (id: string, directionId?: string) =>
    `${BASE}/projects/${id}/export.md${directionId ? `?direction_id=${directionId}` : ''}`,
  tokensJsonUrl: (id: string, directionId?: string) =>
    `${BASE}/projects/${id}/tokens.json${directionId ? `?direction_id=${directionId}` : ''}`,
  tokensCssUrl: (id: string, directionId?: string) =>
    `${BASE}/projects/${id}/tokens.css${directionId ? `?direction_id=${directionId}` : ''}`,
};

export type Api = typeof api;
