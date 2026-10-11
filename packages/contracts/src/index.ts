import { z } from 'zod';
import protocol from '../protocol.schema.json';

export const methods = protocol.properties.method.enum;
export type Method = 'workspace.get' | 'onboarding.complete' | 'documents.import' | 'documents.bookmarks'
  | 'chapters.create' | 'reader.page' | 'notes.save' | 'notes.search' | 'notes.versions' | 'notes.restore'
  | 'settings.save' | 'settings.delete_key' | 'generation.prepare' | 'generation.start' | 'tasks.get'
  | 'export.obsidian' | 'backup.create';
export const requestSchema = z.object({
  protocol_version: z.literal(1), id: z.string().min(1).max(80),
  method: z.string().refine(value => methods.includes(value)), params: z.record(z.string(), z.unknown()),
}).strict();
export const responseSchema = z.discriminatedUnion('ok', [
  z.object({ protocol_version: z.literal(1), id: z.string(), ok: z.literal(true), result: z.unknown() }).strict(),
  z.object({ protocol_version: z.literal(1), id: z.string(), ok: z.literal(false),
    error: z.object({ code: z.string(), message: z.string() }).strict() }).strict(),
]);
export type IPCRequest = z.infer<typeof requestSchema>;
export type IPCResponse = z.infer<typeof responseSchema>;
export type Document = { id: number; title: string; kind: string; course: string; year: string; pages: number; status: string };
export type Chapter = { id: number; document_id: number; title: string; start_page: number; end_page: number; text: string };
export type Note = { id: number; title: string; body: string; sources: string[]; tags: string[]; kind: string; updated_at: string };
export type AIConfig = { base_url: string; model: string; secondary_model: string; daily_budget: number;
  input_price: number; output_price: number; secondary_input_price: number; secondary_output_price: number; max_output_tokens: number };
export type Workspace = { version: string; schema_version: number; data_directory: string; onboarding_complete: boolean;
  documents: Document[]; chapters: Chapter[]; notes: Note[]; topics: {id:number; name:string; note_count:number}[];
  config: AIConfig; key_configured: boolean; spent: number };
export type Prepared = { token: string; prompt: string; amount: number; cached: boolean; model: string; endpoint: string };
export type Task = { id: string; status: 'queued'|'running'|'completed'|'failed'; result?: {note_id?:number;cached:boolean;amount:number}; error?:string };
