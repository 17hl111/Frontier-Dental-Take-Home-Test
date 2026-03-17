// Type hints for helper_edit.d/*.js
export type FileCtx = { uri: string; text: string; lines: string[] };
export type Position = { line: number; character: number };
export type Range = { start: Position; end: Position };
export type NodeCtx = { kind: string; name?: string; line: number; range: Range; text: string };
export type BaselineCtx = FileCtx | null;
export type HelperFn = (node: NodeCtx, file: FileCtx, baseline?: BaselineCtx) => any;
declare const helpers: Record<string, HelperFn>;
export = helpers;
