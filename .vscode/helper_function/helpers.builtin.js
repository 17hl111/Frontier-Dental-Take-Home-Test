"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.helpers = exports.coreHelpers = void 0;
exports.stripComments = stripComments;
exports.maskStrings = maskStrings;
/* ----------------- Comments / string handling ----------------- */
// Remove // and /* */ comments (replace with spaces to preserve line/column)
/**
 * Remove line and block comments while preserving line and column positions.
 * Replaces comment characters with spaces but keeps newlines intact.
 * Tracks string literals and escape sequences so comment markers inside strings are ignored.
 * Not a full parser: nested block comments are not supported.
 */
function stripComments(src) {
    let out = '';
    let inSL = false;
    let inML = false;
    let inStr = false;
    let strCh = '';
    const n = src.length;
    for (let i = 0; i < n; i++) {
        const c = src[i];
        const next = i + 1 < n ? src[i + 1] : '';
        if (inStr) {
            out += c;
            if (c === strCh) {
                inStr = false;
            }
            else if (c === '\\' && next) {
                out += next;
                i++;
            }
            continue;
        }
        if (inSL) {
            if (c === '\n') {
                inSL = false;
                out += c;
            }
            else {
                out += ' ';
            }
            continue;
        }
        if (inML) {
            if (c === '*' && next === '/') {
                inML = false;
                out += '  ';
                i++;
            }
            else if (c === '\n') {
                out += '\n';
            }
            else {
                out += ' ';
            }
            continue;
        }
        if (c === '"' || c === "'") {
            inStr = true;
            strCh = c;
            out += c;
            continue;
        }
        if (c === '/' && next === '/') {
            out += '  ';
            i++;
            inSL = true;
            continue;
        }
        if (c === '/' && next === '*') {
            out += '  ';
            i++;
            inML = true;
            continue;
        }
        out += c;
    }
    return out;
}
// Preserve string boundaries and mask contents with spaces (for keyword search)
/**
 * Mask string literal contents with spaces while keeping quote characters and newlines.
 * This lets regex searches ignore keywords that appear inside strings.
 * Handles escape sequences by consuming the escaped character.
 */
function maskStrings(src) {
    let out = '';
    let inStr = false;
    let quote = '';
    const n = src.length;
    for (let i = 0; i < n; i++) {
        const c = src[i];
        if (!inStr && (c === '"' || c === "'")) {
            inStr = true;
            quote = c;
            out += c;
            continue;
        }
        if (inStr) {
            if (c === '\\') {
                out += '\\';
                if (i + 1 < n) {
                    out += ' ';
                    i++;
                }
            }
            else if (c === quote) {
                inStr = false;
                quote = '';
                out += c;
            }
            else if (c === '\n') {
                out += '\n';
            }
            else {
                out += ' ';
            }
            continue;
        }
        out += c;
    }
    return out;
}
/* ----------------- General utilities ----------------- */
/**
 * Trim whitespace and remove matching surrounding quotes (single or double).
 * If the string is not quoted, return the trimmed value unchanged.
 */
function stripQuotes(raw) {
    const s = raw.trim();
    if ((s.startsWith('"') && s.endsWith('"')) ||
        (s.startsWith("'") && s.endsWith("'"))) {
        return s.slice(1, -1).trim();
    }
    return s;
}
/**
 * Convert a range token to a number when possible.
 * Returns NaN for empty tokens or for the YANG sentinels "min" and "max".
 * Accepts integers and decimals only.
 */
function toNum(t) {
    t = String(t || '').trim();
    if (!t)
        return NaN;
    const lower = t.toLowerCase();
    if (lower === 'min' || lower === 'max')
        return NaN;
    if (/^-?\d+(\.\d+)?$/.test(t))
        return Number(t);
    return NaN;
}
/**
 * Compare two numbers with special handling for NaN.
 * NaN is treated as greater than any real number so it sorts last.
 * Used for ordering ranges that may use infinities.
 */
function cmpNum(a, b) {
    if (isNaN(a) && isNaN(b))
        return 0;
    if (isNaN(a))
        return 1;
    if (isNaN(b))
        return -1;
    return a - b;
}
/**
 * Parse a range segment like "a..b" or a single value like "a".
 * Maps "min" and "max" to -Infinity and +Infinity.
 * Returns null for invalid segments.
 */
function parseRangePart(part) {
    const p = part.trim();
    if (!p)
        return null;
    const segs = p.split('..');
    if (segs.length === 1) {
        const v = toNum(segs[0]);
        if (isNaN(v))
            return null;
        return [v, v];
    }
    if (segs.length === 2) {
        const lo = toNum(segs[0]);
        const hi = toNum(segs[1]);
        if (isNaN(lo) && isNaN(hi))
            return null;
        return [
            isNaN(lo) ? Number.NEGATIVE_INFINITY : lo,
            isNaN(hi) ? Number.POSITIVE_INFINITY : hi
        ];
    }
    return null;
}
/**
 * Sort ranges by start and merge overlaps into a minimal set.
 * Uses cmpNum so infinities are ordered consistently.
 * This simplifies later range comparisons.
 */
function normalizeRanges(ranges) {
    if (!ranges.length)
        return [];
    const sorted = [...ranges].sort((a, b) => cmpNum(a[0], b[0]) || cmpNum(a[1], b[1]));
    const out = [];
    for (const [s, e] of sorted) {
        if (!out.length) {
            out.push([s, e]);
            continue;
        }
        const last = out[out.length - 1];
        if (cmpNum(s, last[1]) <= 0) {
            if (cmpNum(e, last[1]) > 0) {
                last[1] = e;
            }
        }
        else {
            out.push([s, e]);
        }
    }
    return out;
}
/**
 * Parse a union expression such as "1..3 | 7..9".
 * Splits on "|", parses each part, then merges overlaps.
 * Invalid parts are ignored.
 */
function parseUnion(expr) {
    const parts = expr.split('|');
    const ranges = [];
    for (const p of parts) {
        const r = parseRangePart(p);
        if (r)
            ranges.push(r);
    }
    return normalizeRanges(ranges);
}
// Whether base is looser than curr (i.e., curr became stricter)
/**
 * Decide if the current range is stricter than the baseline.
 * Compares overall min and max across all ranges.
 * If min increases or max decreases, the constraint is stricter.
 */
function isStricter(curr, base) {
    if (!curr.length || !base.length)
        return false;
    const bMin = Math.min(...base.map(p => p[0]));
    const bMax = Math.max(...base.map(p => p[1]));
    const cMin = Math.min(...curr.map(p => p[0]));
    const cMax = Math.max(...curr.map(p => p[1]));
    if (cmpNum(cMin, bMin) > 0)
        return true;
    if (cmpNum(cMax, bMax) < 0)
        return true;
    return false;
}
/**
 * Extract raw "range" or "length" expressions from a statement block.
 * Uses a regex that captures text up to the semicolon.
 * Strips surrounding quotes or parentheses when present.
 */
function extractRangeLikeExpressions(block, keyword) {
    const out = [];
    const re = new RegExp(`\\b${keyword}\\s+(.+?);`, 'gi');
    let m;
    while ((m = re.exec(block)) !== null) {
        const raw = m[1];
        const inner = raw.replace(/^[("']+/, '').replace(/["')]+$/, '');
        out.push(inner);
    }
    return out;
}
/* ----------------- Header / baseline helpers ----------------- */
function collectTopLevelIdentifiers(block) {
    const out = new Set();
    const masked = maskStrings(block);
    const start = masked.indexOf('{');
    if (start < 0)
        return out;
    let depth = 0;
    let ident = '';
    const flush = () => {
        if (ident && depth === 1)
            out.add(ident.toLowerCase());
        ident = '';
    };
    for (let i = start; i < masked.length; i++) {
        const ch = masked[i];
        if (ch === '{') {
            flush();
            depth++;
            continue;
        }
        if (ch === '}') {
            flush();
            depth--;
            if (depth <= 0)
                break;
            continue;
        }
        if (depth !== 1) {
            if (!/[A-Za-z0-9_-]/.test(ch))
                ident = '';
            continue;
        }
        if (/[A-Za-z0-9_-]/.test(ch))
            ident += ch;
        else
            flush();
    }
    flush();
    return out;
}
function extractStatementFrom(source, masked, startIndex) {
    if (startIndex < 0)
        return null;
    let depth = 0;
    for (let i = startIndex; i < masked.length; i++) {
        const ch = masked[i];
        if (ch === '{') {
            depth++;
            continue;
        }
        if (ch === '}') {
            if (depth > 0)
                depth--;
            if (depth === 0) {
                return { text: source.slice(startIndex, i + 1), end: i + 1 };
            }
            continue;
        }
        if (ch === ';' && depth === 0) {
            return { text: source.slice(startIndex, i + 1), end: i + 1 };
        }
    }
    return null;
}
function extractTopLevelStatements(block, keyword) {
    const masked = maskStrings(block);
    const start = masked.indexOf('{');
    if (start < 0)
        return [];
    const out = [];
    let depth = 0;
    let ident = '';
    let identStart = -1;
    const flush = (i) => {
        if (ident && depth === 1 && ident.toLowerCase() === keyword.toLowerCase()) {
            const stmt = extractStatementFrom(block, masked, identStart);
            if (stmt) {
                out.push(stmt.text);
            }
        }
        ident = '';
        identStart = -1;
    };
    for (let i = start; i < masked.length; i++) {
        const ch = masked[i];
        if (ch === '{') {
            flush(i);
            depth++;
            continue;
        }
        if (ch === '}') {
            flush(i);
            depth--;
            if (depth <= 0)
                break;
            continue;
        }
        if (depth !== 1) {
            if (!/[A-Za-z0-9_-]/.test(ch))
                ident = '';
            continue;
        }
        if (/[A-Za-z0-9_-]/.test(ch)) {
            if (!ident)
                identStart = i;
            ident += ch;
        }
        else {
            flush(i);
        }
    }
    flush(masked.length);
    return out;
}
function blockHasTopLevelKeyword(block, kw) {
    return collectTopLevelIdentifiers(block).has(kw.toLowerCase());
}
function allRevisionsHaveSummaryInBlock(block) {
    const revs = extractTopLevelStatements(block, 'revision');
    if (!revs.length)
        return true;
    for (const stmt of revs) {
        if (!stmt.includes('{'))
            return false;
        if (!blockHasTopLevelKeyword(stmt, 'description'))
            return false;
    }
    return true;
}
function moduleHeaderFieldsOkNode(node, file) {
    if (!node || node.kind !== 'module-header')
        return true;
    const block = extractBlockForNode(file, node);
    if (!block)
        return true;
    const hasPrefix = blockHasTopLevelKeyword(block, 'prefix');
    const hasOrg = blockHasTopLevelKeyword(block, 'organization');
    const hasContact = blockHasTopLevelKeyword(block, 'contact');
    const hasRevision = blockHasTopLevelKeyword(block, 'revision');
    if (!hasPrefix || !hasOrg || !hasContact || !hasRevision)
        return false;
    return allRevisionsHaveSummaryInBlock(block);
}
// Concatenate all revision blocks as a "revision signature" for change checks
/**
 * Concatenate all revision statements into a single signature string.
 * Used to compare baseline vs current module revisions.
 * Brace depth scanning ensures full block content is included.
 */
function extractRevisionSignature(file) {
    const text = file.text;
    const re = /revision\s+"?([\d-]+)"?\s*([;{])/gi;
    let m;
    const parts = [];
    while ((m = re.exec(text)) !== null) {
        const sep = m[2];
        if (sep === ';') {
            parts.push(text.slice(m.index, re.lastIndex));
        }
        else {
            let idx = re.lastIndex;
            let depth = 1;
            while (idx < text.length && depth > 0) {
                const ch = text[idx++];
                if (ch === '{')
                    depth++;
                else if (ch === '}')
                    depth--;
            }
            parts.push(text.slice(m.index, idx));
        }
    }
    if (!parts.length)
        return null;
    return parts.join('\n');
}
/**
 * Node-based module name validator (for multiple module statements).
 * If the node is not a module header, returns true to avoid false positives.
 */
function moduleNameHasTelusPrefixNode(node) {
    if (!node || node.kind !== 'module-header')
        return true;
    const raw = String(node.name ?? '').trim();
    const name = stripQuotes(raw);
    if (!name)
        return true;
    return name.startsWith('tinaa-') || name.startsWith('telus-');
}
/**
 * Node-based namespace validator (for multiple namespace statements).
 * If the node is not a namespace, returns true to avoid false positives.
 */
function namespaceStartsWithTinaaNode(node) {
    if (!node || node.kind !== 'namespace')
        return true;
    const raw = String(node.name ?? '').trim();
    const ns = stripQuotes(raw);
    if (!ns)
        return true;
    return ns.startsWith('https://tinaa.telus.com');
}
function findNearestModuleHeaderLine(file, fromLine) {
    for (let i = fromLine; i >= 0; i--) {
        if (/^\s*(module|submodule)\b/i.test(file.lines[i] || '')) {
            return i;
        }
    }
    return null;
}
function parseModuleNameFromLine(line) {
    const m = line.match(/^\s*(module|submodule)\s+([A-Za-z0-9_\-\.]+)\b/);
    if (!m)
        return null;
    return stripQuotes(m[2]);
}
function getModuleNameForLine(file, line) {
    const moduleLine = findNearestModuleHeaderLine(file, line);
    if (moduleLine === null)
        return null;
    return parseModuleNameFromLine(file.lines[moduleLine] || '');
}
function getAugDevModeForLine(file, line) {
    const name = getModuleNameForLine(file, line);
    if (name) {
        if (name.startsWith('tinaa-aug'))
            return 'aug';
        if (name.startsWith('tinaa-dev'))
            return 'dev';
    }
    if (isAugModuleFile(file))
        return 'aug';
    if (isDevModuleFile(file))
        return 'dev';
    return null;
}
function isTopLevelStatementInModule(file, moduleLine, targetLine) {
    if (targetLine < moduleLine)
        return false;
    let depth = 0;
    for (let i = moduleLine; i <= targetLine; i++) {
        const masked = maskStrings(file.lines[i] || '');
        for (let j = 0; j < masked.length; j++) {
            const ch = masked[j];
            if (ch === '{')
                depth++;
            else if (ch === '}')
                depth = Math.max(0, depth - 1);
        }
    }
    return depth === 1;
}
/**
 * Validate that the module prefix starts with "telus-".
 * Ignores non-module-level prefix statements.
 */
function modulePrefixHasTelusPrefixNode(node, file) {
    if (!node || node.kind !== 'prefix')
        return true;
    if (typeof node.line !== 'number')
        return true;
    const moduleLine = findNearestModuleHeaderLine(file, node.line);
    if (moduleLine === null)
        return true;
    if (!isTopLevelStatementInModule(file, moduleLine, node.line))
        return true;
    const raw = String(node.name ?? '').trim();
    const name = stripQuotes(raw);
    if (!name)
        return true;
    return name.startsWith('telus-');
}
/* ----------------- aug/dev module naming ----------------- */
/**
 * Extract the file name without the .yang extension from a URI/path.
 * Falls back to the last path segment if the extension is missing.
 */
function getFileBaseName(file) {
    const uri = file.uri || '';
    const m = uri.match(/([^/\\]+)\.yang$/i);
    if (m)
        return m[1];
    const segs = uri.split(/[\\/]/);
    return segs[segs.length - 1] || uri;
}
/**
 * Detect aug module file naming conventions.
 * Matches "-aug" or "-aug@YYYYMMDD" suffixes.
 */
function isAugModuleFile(file) {
    const name = getFileBaseName(file);
    return /-aug(@\d{8})?$/.test(name);
}
/**
 * Detect dev module file naming conventions.
 * Matches "-dev" or "-dev@YYYYMMDD" suffixes.
 */
function isDevModuleFile(file) {
    const name = getFileBaseName(file);
    return /-dev(@\d{8})?$/.test(name);
}
/**
 * For aug/dev files, enforce module name prefix rules.
 * Requires "tinaa-aug" for aug files and "tinaa-dev" for dev files.
 * Missing module name is treated as invalid.
 */
/**
 * Node-based aug/dev module name validator (for multiple module statements).
 */
function strictAugDevModuleNameBadNode(node, file) {
    if (!node || node.kind !== 'module-header')
        return false;
    const isAug = isAugModuleFile(file);
    const isDev = isDevModuleFile(file);
    if (!isAug && !isDev)
        return false;
    const raw = String(node.name ?? '').trim();
    const name = stripQuotes(raw);
    if (!name)
        return true;
    if (isAug)
        return !name.startsWith('tinaa-aug');
    return !name.startsWith('tinaa-dev');
}
/**
 * For aug/dev files, enforce namespace URL prefixes.
 * Requires /yang/aug for aug and /yang/dev for dev files.
 * Missing namespace is treated as invalid.
 */
/**
 * Node-based aug/dev namespace validator (for multiple namespace statements).
 */
function strictAugDevNamespaceBadNode(node, file) {
    if (!node || node.kind !== 'namespace')
        return false;
    if (typeof node.line !== 'number')
        return false;
    const mode = getAugDevModeForLine(file, node.line);
    if (!mode)
        return false;
    const raw = String(node.name ?? '').trim();
    const ns = stripQuotes(raw);
    if (!ns)
        return true;
    if (mode === 'aug')
        return !ns.startsWith('https://tinaa.telus.com/yang/aug');
    return !ns.startsWith('https://tinaa.telus.com/yang/dev');
}
/**
 * Validate the module-level prefix for aug/dev modules.
 * Only checks the prefix statement on the module header line.
 * Requires "telus-aug" or "telus-dev" depending on file type.
 */
function augDevPrefixNamingBad(node, file) {
    if (!node || node.kind !== 'prefix')
        return false;
    if (typeof node.line !== 'number')
        return false;
    const mode = getAugDevModeForLine(file, node.line);
    if (!mode)
        return false;
    const moduleLine = findNearestModuleHeaderLine(file, node.line);
    if (moduleLine === null)
        return false;
    if (!isTopLevelStatementInModule(file, moduleLine, node.line))
        return false;
    const raw = String(node.name ?? '').trim();
    const name = stripQuotes(raw);
    if (!name)
        return true;
    if (mode === 'aug')
        return !name.startsWith('telus-aug');
    return !name.startsWith('telus-dev');
}
/* ----------------- Node-based block / parent lookup ----------------- */
/**
 * Extract the statement block for a node starting at its line.
 * Uses brace depth to capture multi-line blocks and stops at the matching closing brace.
 * For single-line statements ending with ";", returns just that line.
 */
function extractBlockForNode(file, node) {
    if (!node || typeof node.line !== 'number')
        return null;
    const lines = file.lines;
    let i = node.line;
    if (i < 0 || i >= lines.length)
        return null;
    let block = '';
    let depth = 0;
    let started = false;
    for (; i < lines.length; i++) {
        const L = lines[i];
        if (!started) {
            block += L + '\n';
            if (L.includes('{')) {
                depth += (L.match(/{/g) || []).length;
                depth -= (L.match(/}/g) || []).length;
                started = true;
            }
            else if (L.includes(';')) {
                break;
            }
            if (started && depth <= 0)
                break;
            continue;
        }
        block += L + '\n';
        depth += (L.match(/{/g) || []).length;
        depth -= (L.match(/}/g) || []).length;
        if (depth <= 0)
            break;
    }
    return block;
}
/**
 * Walk upward by indentation to find the nearest parent container.
 * Assumes indentation reflects hierarchy (heuristic, not a full parser).
 */
function findParentContainerForLeaf(node, file) {
    if (!node || typeof node.line !== 'number')
        return null;
    const lines = file.lines;
    const leafLine = node.line;
    const leafText = lines[leafLine] ?? '';
    const leafIndent = (leafText.match(/^\s*/) || [''])[0].length;
    for (let i = leafLine - 1; i >= 0; i--) {
        const L = lines[i];
        if (!L.trim())
            continue;
        const indent = (L.match(/^\s*/) || [''])[0].length;
        if (indent < leafIndent) {
            const m = L.match(/^\s*container\s+([A-Za-z0-9_\-]+)\b/);
            if (m)
                return { line: i, name: m[1] };
        }
    }
    return null;
}
/**
 * Walk upward to find the nearest parent list for a leaf.
 * Stops and returns null if a container is found before any list.
 * Uses indentation as a heuristic for structure.
 */
function findParentListForLeaf(node, file) {
    if (!node || typeof node.line !== 'number')
        return null;
    const lines = file.lines;
    const leafLine = node.line;
    const leafText = lines[leafLine] ?? '';
    const leafIndent = (leafText.match(/^\s*/) || [''])[0].length;
    for (let i = leafLine - 1; i >= 0; i--) {
        const L = lines[i];
        if (!L.trim())
            continue;
        const indent = (L.match(/^\s*/) || [''])[0].length;
        if (indent < leafIndent) {
            const m = L.match(/^\s*list\s+([A-Za-z0-9_\-]+)\b/);
            if (m)
                return { line: i, name: m[1] };
            const m2 = L.match(/^\s*container\s+([A-Za-z0-9_\-]+)\b/);
            if (m2)
                return null;
        }
    }
    return null;
}
/* ----------------- description helper ----------------- */
/**
 * Check whether a node block contains a description statement.
 * Masks strings to avoid matching "description" inside quotes.
 */
function hasDescriptionInBlock(node, file) {
    const block = extractBlockForNode(file, node);
    if (!block)
        return false;
    const masked = maskStrings(block);
    return /\bdescription\b[^;]*;/i.test(masked);
}
/* ----------------- create：mandatory leaf under presence container ----------------- */
/**
 * Detect mandatory leaves that are not under a presence container.
 * If the leaf is mandatory true and the parent container lacks presence, returns true.
 */
function mandatoryLeafNotUnderPresenceContainer(node, file) {
    if (!node || node.kind !== 'leaf')
        return false;
    const block = extractBlockForNode(file, node);
    if (!block)
        return false;
    if (!/\bmandatory\s+true\s*;/i.test(block))
        return false;
    const parent = findParentContainerForLeaf(node, file);
    if (!parent)
        return true;
    const cNode = { kind: 'container', name: parent.name, line: parent.line };
    let cBlock = extractBlockForNode(file, cNode);
    if (!cBlock)
        return true;
    cBlock = maskStrings(cBlock);
    return !/\bpresence\b[^;]*;/i.test(cBlock);
}
/* ----------------- create: key leaf description (first 5 lines) ----------------- */
/**
 * Determine if a leaf is part of its parent list key.
 * Parses the list "key" statement and checks the leaf name.
 */
function isKeyLeaf(node, file) {
    if (!node || node.kind !== 'leaf' || !node.name)
        return false;
    const parent = findParentListForLeaf(node, file);
    if (!parent)
        return false;
    const listNode = { kind: 'list', name: parent.name, line: parent.line };
    const block = extractBlockForNode(file, listNode);
    if (!block)
        return false;
    const m = block.match(/^\s*key\s+"?([^"]+)"?\s*;/m);
    if (!m)
        return false;
    const keyNames = m[1].trim().split(/\s+/);
    return keyNames.includes(node.name);
}
/**
 * Require a description within the first 5 lines of a key leaf block.
 * Masks strings before searching for the description keyword.
 */
function keyLeafDescriptionMissingWithin5Lines(node, file) {
    if (!isKeyLeaf(node, file))
        return false;
    const block = extractBlockForNode(file, node);
    if (!block)
        return true;
    const first = block.split(/\r?\n/).slice(0, 5).join('\n');
    const masked = maskStrings(first);
    // Allow description without semicolon; accept end-of-line or closing brace as terminator.
    return !/\bdescription\b[^\n;}]*([;}]|$)/i.test(masked);
}
/* ----------------- import prefix helpers ----------------- */
/**
 * Parse import blocks and map module names to their prefixes.
 * Uses a dot-all regex to span across newlines inside import blocks.
 */
function parseImportPrefixMap(file) {
    const text = file.text;
    const re = /import\s+([A-Za-z0-9_\-]+)\s*\{[^}]*?\bprefix\s+(.+?);[^}]*?\}/gsi;
    const map = {};
    let m;
    while ((m = re.exec(text)) !== null) {
        const moduleName = m[1];
        const prefixRaw = m[2];
        map[moduleName] = stripQuotes(prefixRaw);
    }
    return map;
}
/**
 * Detect leftover references using a given prefix (oldPrefix:xxx).
 * Simple text scan using a word-boundary regex.
 */
function hasDanglingPrefixUse(file, oldPrefix) {
    if (!oldPrefix)
        return false;
    const re = new RegExp(`\\b${oldPrefix}\\s*:`);
    return re.test(file.text);
}
/**
 * Compare module prefix between baseline and current files.
 * If the prefix changed and old prefix usage remains, returns true.
 */
function extractModuleBlockByName(file, name) {
    const re = new RegExp(`^\\s*(module|submodule)\\s+${name}\\b`, 'm');
    const lines = file.lines;
    for (let i = 0; i < lines.length; i++) {
        if (!re.test(lines[i]))
            continue;
        const node = { line: i };
        const block = extractBlockForNode(file, node);
        if (block)
            return block;
    }
    return null;
}
function getModuleOccurrenceIndex(file, node) {
    if (!node || typeof node.line !== 'number')
        return null;
    const raw = String(node.name ?? '').trim();
    const name = stripQuotes(raw);
    if (!name)
        return null;
    let idx = -1;
    for (let i = 0; i <= node.line && i < file.lines.length; i++) {
        const n = parseModuleNameFromLine(file.lines[i] || '');
        if (n && n === name)
            idx++;
        if (i === node.line)
            return idx >= 0 ? idx : null;
    }
    return null;
}
function extractModuleBlockByNameIndex(file, name, index) {
    let idx = -1;
    for (let i = 0; i < file.lines.length; i++) {
        const n = parseModuleNameFromLine(file.lines[i] || '');
        if (n && n === name) {
            idx++;
            if (idx === index) {
                const block = extractBlockForNode(file, { line: i });
                if (block)
                    return block;
                return null;
            }
        }
    }
    return null;
}
function getModuleIndexForLine(file, line) {
    const moduleLine = findNearestModuleHeaderLine(file, line);
    if (moduleLine === null)
        return null;
    const name = parseModuleNameFromLine(file.lines[moduleLine] || '');
    if (!name)
        return null;
    let idx = -1;
    for (let i = 0; i <= moduleLine && i < file.lines.length; i++) {
        const n = parseModuleNameFromLine(file.lines[i] || '');
        if (n && n === name)
            idx++;
    }
    if (idx < 0)
        return null;
    return { name, index: idx };
}
function getBaselineModuleBlockForLine(current, baseline, line) {
    const info = getModuleIndexForLine(current, line);
    if (!info)
        return null;
    const byIndex = extractModuleBlockByNameIndex(baseline, info.name, info.index);
    if (byIndex)
        return byIndex;
    return extractModuleBlockByName(baseline, info.name);
}
function fileCtxFromBlock(base, block) {
    return { uri: base.uri + '#module', text: block, lines: block.split(/\r?\n/) };
}
function parseModulePrefixInBlock(block) {
    const stmts = extractTopLevelStatements(block, 'prefix');
    if (!stmts.length)
        return null;
    const m = stmts[0].match(/^\s*prefix\s+(.+?);/m);
    if (!m)
        return null;
    return stripQuotes(m[1]);
}
function hasDanglingPrefixUseInBlock(block, oldPrefix) {
    if (!oldPrefix)
        return false;
    const re = new RegExp(`\\b${oldPrefix}\\s*:`);
    return re.test(block);
}
function modulePrefixChangedButRefsNotUpdatedNode(node, file, baseline) {
    if (!node || node.kind !== 'module-header')
        return false;
    if (!baseline || !baseline.text)
        return false;
    const currBlock = extractBlockForNode(file, node);
    if (!currBlock)
        return false;
    const rawName = String(node.name ?? '').trim();
    const name = stripQuotes(rawName);
    const idx = getModuleOccurrenceIndex(file, node);
    let baseBlock = null;
    if (name && idx !== null) {
        baseBlock = extractModuleBlockByNameIndex(baseline, name, idx);
    }
    if (!baseBlock && name) {
        baseBlock = extractModuleBlockByName(baseline, name);
    }
    if (!baseBlock)
        return false;
    const newP = parseModulePrefixInBlock(currBlock);
    const oldP = parseModulePrefixInBlock(baseBlock);
    if (!oldP || !newP || oldP === newP)
        return false;
    return hasDanglingPrefixUseInBlock(currBlock, oldP);
}
/**
 * Diff rule for a single import node:
 * - In baseline, the import prefix = oldP
 * - In current file, the import prefix = newP
 * - If oldP != newP and the file still uses oldP:xxx -> return true
 */
/**
 * Compare an import prefix between baseline and current for a specific import.
 * If changed and old prefix usage remains anywhere, returns true.
 */
function importPrefixChangedButRefsNotUpdated(node, file, baseline) {
    if (!node || node.kind !== 'import' || !baseline || !baseline.text) {
        return false;
    }
    const text = file.text;
    const baseText = baseline.text;
    const mCurr = text.match(new RegExp(`import\\s+${node.name}\\s*\\{[\\s\\S]*?\\bprefix\\s+(.+?);[\\s\\S]*?\\}`, 'i'));
    const mBase = baseText.match(new RegExp(`import\\s+${node.name}\\s*\\{[\\s\\S]*?\\bprefix\\s+(.+?);[\\s\\S]*?\\}`, 'i'));
    if (!mCurr || !mBase)
        return false;
    const newP = stripQuotes(mCurr[1]);
    const oldP = stripQuotes(mBase[1]);
    if (!oldP || !newP || oldP === newP)
        return false;
    return hasDanglingPrefixUse(file, oldP);
}
/* ----------------- update: range / length tightening ----------------- */
/**
 * Check range/length constraints for a node against baseline.
 * Parses union ranges and detects if the new constraint is narrower.
 */
function constraintsBecameStricterForNode(node, file, baseline) {
    if (!baseline || !baseline.text || !node?.name)
        return false;
    const currBlock = extractBlockForNode(file, node);
    const baseBlock = extractBlockForNode(baseline, node);
    if (!currBlock || !baseBlock)
        return false;
    for (const k of ['range', 'length']) {
        const currExprs = extractRangeLikeExpressions(currBlock, k);
        const baseExprs = extractRangeLikeExpressions(baseBlock, k);
        if (!currExprs.length || !baseExprs.length)
            continue;
        const currRanges = currExprs.flatMap(parseUnion);
        const baseRanges = baseExprs.flatMap(parseUnion);
        if (isStricter(currRanges, baseRanges))
            return true;
    }
    return false;
}
/* >>> Baseline-based state node info (for diff rules) <<< */
/**
 * Find a leaf within an optional container/list scope.
 * Returns whether it exists and whether it is config false.
 * Uses brace matching to limit the search to the container block.
 */
function leafConfigInfo(file, containerName, leafName) {
    const text = file.text;
    let scope = text;
    if (containerName) {
        const reCont = new RegExp(`^\\s*(container|list)\\s+${containerName}\\b`, 'm');
        const m = text.match(reCont);
        if (!m)
            return { exists: false, configFalse: false };
        const start = text.indexOf(m[0]);
        if (start >= 0) {
            let idx = text.indexOf('{', start);
            if (idx >= 0) {
                let depth = 1;
                let j = idx + 1;
                while (j < text.length && depth > 0) {
                    const ch = text[j++];
                    if (ch === '{')
                        depth++;
                    else if (ch === '}')
                        depth--;
                }
                scope = text.slice(start, j);
            }
        }
    }
    const leafRe = new RegExp(`leaf\\s+${leafName}\\b([^{]*\\{([\\s\\S]*?)\\})`, 'm');
    const lm = scope.match(leafRe);
    if (!lm)
        return { exists: false, configFalse: false };
    const body = lm[2] ?? '';
    const masked = maskStrings(body);
    const cfgFalse = /\bconfig\s+false\b\s*;/i.test(masked);
    return { exists: true, configFalse: cfgFalse };
}
/**
 * stateToConfigMandatoryBad:
 *   - In baseline, the leaf is config false (read-only state)
 *   - In current version, the leaf is mandatory (config)
 *   -> violation
 */
/**
 * Detect a leaf that moved from config false to mandatory true.
 * Baseline must show config false; current must be mandatory true.
 * Returns true to indicate a violation.
 */
function stateToConfigMandatoryBad(node, file, baseline) {
    if (!baseline || !baseline.text)
        return false;
    if (!node || node.kind !== 'leaf' || !node.name)
        return false;
    const block = extractBlockForNode(file, node);
    if (!block)
        return false;
    if (!/\bmandatory\s+true\s*;/i.test(block))
        return false;
    const parent = findParentContainerForLeaf(node, file);
    const containerName = parent ? parent.name : null;
    const leafName = node.name;
    const info = leafConfigInfo(baseline, containerName, leafName);
    if (!info.exists || !info.configFalse) {
        return false;
    }
    return true;
}
/* ----------------- update: new mandatory leaf guarding rule ----------------- */
/**
 * Return true if the leaf block contains "mandatory true".
 */
function isLeafMandatory(node, file) {
    const block = extractBlockForNode(file, node);
    if (!block)
        return false;
    return /\bmandatory\s+true\s*;/i.test(block);
}
/**
 * Like leafConfigInfo, but returns whether the leaf is mandatory.
 * Used to compare baseline vs current for mandatory changes.
 */
function leafMandatoryInfo(file, containerName, leafName) {
    const text = file.text;
    let scope = text;
    if (containerName) {
        const reCont = new RegExp(`^\\s*(container|list)\\s+${containerName}\\b`, 'm');
        const m = text.match(reCont);
        if (!m)
            return { exists: false, mandatory: false };
        const start = text.indexOf(m[0]);
        if (start >= 0) {
            let idx = text.indexOf('{', start);
            if (idx >= 0) {
                let depth = 1;
                let j = idx + 1;
                while (j < text.length && depth > 0) {
                    const ch = text[j++];
                    if (ch === '{')
                        depth++;
                    else if (ch === '}')
                        depth--;
                }
                scope = text.slice(start, j);
            }
        }
    }
    const leafRe = new RegExp(`leaf\\s+${leafName}\\b([^{]*\\{([\\s\\S]*?)\\})`, 'm');
    const lm = scope.match(leafRe);
    if (!lm)
        return { exists: false, mandatory: false };
    const body = lm[2] ?? '';
    return { exists: true, mandatory: /\bmandatory\s+true\s*;/i.test(body) };
}
/**
 * Check if the leaf is under a parent container with a presence statement.
 */
function isGuardedByPresenceContainer(node, file) {
    const parent = findParentContainerForLeaf(node, file);
    if (!parent)
        return false;
    const cNode = { kind: 'container', name: parent.name, line: parent.line };
    let cBlock = extractBlockForNode(file, cNode);
    if (!cBlock)
        return false;
    cBlock = maskStrings(cBlock);
    return /\bpresence\b[^;]*;/i.test(cBlock);
}
/**
 * Check whether a leaf has an if-feature statement in its block.
 */
function leafHasIfFeature(node, file) {
    let block = extractBlockForNode(file, node);
    if (!block)
        return false;
    block = maskStrings(block);
    return /\bif-feature\b[^;]*;/i.test(block);
}
/**
 * Detect new or newly-mandatory leaves without presence/if-feature guards.
 * If the leaf is new or flipped to mandatory and not guarded, returns true.
 */
function newMandatoryNotGuarded(node, file, baseline) {
    if (!node || node.kind !== 'leaf' || !node.name)
        return false;
    if (!isLeafMandatory(node, file))
        return false;
    const parent = findParentContainerForLeaf(node, file);
    const containerName = parent ? parent.name : null;
    const leafName = node.name;
    let baselineExists = false;
    let baselineMandatory = false;
    if (baseline && typeof baseline.text === 'string' && typeof node.line === 'number') {
        const baseBlock = getBaselineModuleBlockForLine(file, baseline, node.line);
        const baselineCtx = baseBlock ? fileCtxFromBlock(baseline, baseBlock) : baseline;
        const info = leafMandatoryInfo(baselineCtx, containerName, leafName);
        baselineExists = info.exists;
        baselineMandatory = info.mandatory;
    }
    const isNewLeaf = !baselineExists;
    const flipped = baselineExists && !baselineMandatory;
    if (!isNewLeaf && !flipped)
        return false;
    const guarded = isGuardedByPresenceContainer(node, file) || leafHasIfFeature(node, file);
    return !guarded;
}
/* ----------------- material change + revision / reference ----------------- */
/**
 * Extract a reference statement from a block.
 * Returns a flag and the stripped text value.
 */
function referenceInfoFromBlock(block) {
    const re = /\breference\s+(.+?);/is;
    const m = block.match(re);
    if (!m)
        return { exists: false, text: '' };
    const raw = m[1].trim();
    return { exists: true, text: stripQuotes(raw) };
}
/**
 * materialChangeMissingRevisionRef:
 *   - Used in update mode:
 *     1. A node's block has a material change vs baseline (content differs).
 *     2. Require both:
 *        - Module-level revision updated (if baseline has one, it must change; if not, add one).
 *        - Reference within the block updated (if baseline has none -> add; if baseline has one -> change content).
 *   - If any requirement fails, return true -> rule triggers.
 */
/**
 * Detect material changes to a node block and enforce revision/reference updates.
 * Compares normalized block text; if changed, requires a new revision and a new or updated reference.
 * Returns true when required updates are missing.
 */
function materialChangeMissingRevisionRef(node, file, baseline) {
    if (!baseline || !baseline.text)
        return false;
    if (!node || typeof node.line !== 'number')
        return false;
    const currBlock = extractBlockForNode(file, node);
    const baseBlock = extractBlockForNode(baseline, node);
    if (!currBlock || !baseBlock)
        return false;
    const normalize = (s) => s.replace(/\s+/g, '').trim();
    // If block text (whitespace removed) is identical, treat as no material change
    if (normalize(currBlock) === normalize(baseBlock)) {
        return false;
    }
    // Module-level revision check
    const currRevisionSig = extractRevisionSignature(file);
    const baseRevisionSig = extractRevisionSignature(baseline);
    const currHasRevision = !!currRevisionSig;
    const baseHasRevision = !!baseRevisionSig;
    let revisionOk = true;
    if (!currHasRevision) {
        // Changed but current file has no revision -> not ok
        revisionOk = false;
    }
    else if (baseHasRevision) {
        // Baseline has revision; require revision content change
        if (currRevisionSig === baseRevisionSig) {
            revisionOk = false;
        }
    }
    else {
        // Baseline has no revision and current has at least one -> OK
        revisionOk = true;
    }
    if (!revisionOk) {
        return true;
    }
    // Reference check inside the block
    const baseRef = referenceInfoFromBlock(baseBlock);
    const currRef = referenceInfoFromBlock(currBlock);
    if (!baseRef.exists && !currRef.exists) {
        // Baseline and current have no reference -> should add, but missing
        return true;
    }
    if (!currRef.exists) {
        // Regardless of baseline, missing reference in current is not ok
        return true;
    }
    if (baseRef.exists && currRef.text === baseRef.text) {
        // Baseline has reference, but content not updated
        return true;
    }
    // Revision + reference requirements satisfied
    return false;
}
/* ----------------- update: do not delete obsolete definitions ----------------- */
/**
 * Collect definitions marked with "status obsolete".
 * Returns a set of "kind:name" keys for comparison.
 */
function collectObsoleteDefinitions(file) {
    const result = new Set();
    const lines = file.lines;
    const defRe = /^\s*(leaf|leaf-list|container|list|typedef|rpc|notification|augment|deviation)\s+([A-Za-z0-9_\-:]+)\b/;
    for (let i = 0; i < lines.length; i++) {
        const L = lines[i];
        const m = L.match(defRe);
        if (!m)
            continue;
        const kind = m[1];
        const name = m[2];
        const node = { line: i };
        const block = extractBlockForNode(file, node);
        if (!block)
            continue;
        if (/\bstatus\s+obsolete\s*;/.test(block)) {
            result.add(`${kind}:${name}`);
        }
    }
    return result;
}
function collectObsoleteDefinitionsInBlock(block) {
    const result = new Set();
    const blockFile = {
        uri: 'block://module',
        text: block,
        lines: block.split(/\r?\n/),
    };
    const lines = blockFile.lines;
    const defRe = /^\s*(leaf|leaf-list|container|list|typedef|rpc|notification|augment|deviation)\s+([A-Za-z0-9_\-:]+)\b/;
    for (let i = 0; i < lines.length; i++) {
        const L = lines[i];
        const m = L.match(defRe);
        if (!m)
            continue;
        const kind = m[1];
        const name = m[2];
        const node = { line: i };
        const defBlock = extractBlockForNode(blockFile, node);
        if (!defBlock)
            continue;
        if (/\bstatus\s+obsolete\b/i.test(defBlock)) {
            result.add(`${kind}:${name}`);
        }
    }
    return result;
}
/**
 * obsoleteDefinitionsRemoved:
 *   - Baseline has definitions marked as status obsolete.
 *   - Update file removes them (or renames so the same name/kind is missing).
 *   - Return true to report a warning on module-header.
 */
/**
 * Detect when obsolete definitions were removed between baseline and current.
 * If any baseline obsolete definition is missing, returns true.
 */
function obsoleteDefinitionsRemovedNode(node, file, baseline) {
    if (!node || node.kind !== 'module-header')
        return false;
    if (!baseline || !baseline.text)
        return false;
    const currBlock = extractBlockForNode(file, node);
    const rawName = String(node.name ?? '').trim();
    const name = stripQuotes(rawName);
    const idx = getModuleOccurrenceIndex(file, node);
    let baseBlock = null;
    if (name && idx !== null) {
        baseBlock = extractModuleBlockByNameIndex(baseline, name, idx);
    }
    if (!baseBlock && name) {
        baseBlock = extractModuleBlockByName(baseline, name);
    }
    if (!currBlock || !baseBlock)
        return false;
    const baseSet = collectObsoleteDefinitionsInBlock(baseBlock);
    if (!baseSet.size)
        return false;
    const currSet = collectObsoleteDefinitionsInBlock(currBlock);
    for (const key of baseSet) {
        if (!currSet.has(key))
            return true;
    }
    return false;
}
/* ----------------- create: import block prefix rule ----------------- */
/**
 * Ensure an import block has a prefix statement and that it appears first.
 * Ignores blank lines and comment-only lines when determining the first statement.
 */
function importBlockPrefixNotFirstOrMissing(node, file) {
    if (!node || node.kind !== 'import')
        return false;
    const block = extractBlockForNode(file, node);
    if (!block)
        return false;
    const open = block.indexOf('{');
    const close = block.lastIndexOf('}');
    if (open < 0 || close < 0 || close <= open)
        return false;
    const body = block.slice(open + 1, close);
    const lines = body.split(/\r?\n/);
    const hasPrefixAnywhere = /\bprefix\b/.test(body);
    if (!hasPrefixAnywhere)
        return true;
    let firstMeaningful = null;
    for (const raw of lines) {
        const trimmed = raw.trim();
        if (!trimmed)
            continue;
        if (/^\/\//.test(trimmed))
            continue;
        if (/^\/\*/.test(trimmed))
            continue;
        if (/^\*/.test(trimmed))
            continue;
        if (/^\*\//.test(trimmed))
            continue;
        firstMeaningful = trimmed;
        break;
    }
    if (!firstMeaningful)
        return false;
    return !/^prefix\b/i.test(firstMeaningful);
}
/* ----------------- create: device/NI outer list rule ----------------- */
/**
 * Heuristic: check if a name looks like a device or network-instance container.
 * Matches common separators such as dash or underscore.
 */
function isDeviceNiLikeName(name) {
    if (!name)
        return false;
    const n = name.toLowerCase();
    // Device family, e.g. device, devices, core-device-config, my-device-list
    if (/(^|[-_])device(s)?($|[-_])/.test(n))
        return true;
    // Network-instance family, e.g. network-instance, user-network-instances
    if (/(^|[-_])network-instance(s)?($|[-_])/.test(n))
        return true;
    return false;
}
/**
 * Walk up the file by indentation to find a list ancestor.
 * Stops at container/module and returns false if none is found.
 */
function hasListAncestor(node, file) {
    if (!node || typeof node.line !== 'number')
        return false;
    const lines = file.lines;
    const nodeLine = node.line;
    const nodeText = lines[nodeLine] ?? '';
    const nodeIndent = (nodeText.match(/^\s*/) || [''])[0].length;
    for (let i = nodeLine - 1; i >= 0; i--) {
        const L = lines[i];
        if (!L.trim())
            continue;
        const indent = (L.match(/^\s*/) || [''])[0].length;
        if (indent < nodeIndent) {
            // Find the nearest structural ancestor
            if (/^\s*list\b/i.test(L))
                return true;
            if (/^\s*(container|module|submodule)\b/i.test(L))
                return false;
        }
    }
    return false;
}
/**
 * deviceNiContainerShouldUseOuterList:
 *   - Name belongs to the device or network-instance family.
 *   - No list ancestor is found when walking upward.
 *   - This is considered a container wrapping device/NI directly; prefer an outer list.
 *
 * Return true to indicate a violation (emit warning).
 */
/**
 * Warn when a device or network-instance container is not wrapped by a list.
 * Returns true when an outer list is expected but missing.
 */
function deviceNiContainerShouldUseOuterList(node, file) {
    if (!node || node.kind !== 'container')
        return false;
    if (!isDeviceNiLikeName(node.name))
        return false;
    // Already under a list; treat outer list as present
    if (hasListAncestor(node, file))
        return false;
    return true;
}
/**
 * Analyze a container/list block to see what appears at the top level.
 * Tracks brace depth and token identifiers to detect structured children, leaf-like items, and description.
 * Strings are masked so keywords inside quotes do not confuse the scan.
 */
function analyzeShellBlock(block) {
    const masked = maskStrings(block);
    const start = masked.indexOf('{');
    if (start < 0) {
        return {
            hasStructChild: false,
            hasTopLevelLeafLike: false,
            hasTopLevelDescription: false,
        };
    }
    let depth = 0;
    let ident = '';
    let hasStructChild = false;
    let hasTopLevelLeafLike = false;
    let hasTopLevelDescription = false;
    const flushIdent = () => {
        if (!ident || depth !== 1) {
            ident = '';
            return;
        }
        const id = ident.toLowerCase();
        // Structured nodes in top-level statements
        if (id === 'container' ||
            id === 'list' ||
            id === 'choice' ||
            id === 'uses' ||
            id === 'grouping' ||
            id === 'case') {
            hasStructChild = true;
        }
        // Top-level leaf / leaf-list / rpc / notification
        if (id === 'leaf' ||
            id === 'leaf-list' ||
            id === 'rpc' ||
            id === 'notification') {
            hasTopLevelLeafLike = true;
        }
        // Top-level description (what we care about)
        if (id === 'description') {
            hasTopLevelDescription = true;
        }
        ident = '';
    };
    for (let i = start; i < masked.length; i++) {
        const ch = masked[i];
        if (ch === '{') {
            flushIdent();
            depth++;
            continue;
        }
        if (ch === '}') {
            flushIdent();
            depth--;
            if (depth <= 0)
                break;
            continue;
        }
        if (depth !== 1) {
            // Not in top-level statements; drop the accumulated ident
            if (/[A-Za-z0-9_-]/.test(ch)) {
                // do nothing; ident accumulates only when depth === 1
            }
            else {
                ident = '';
            }
            continue;
        }
        if (/[A-Za-z0-9_-]/.test(ch)) {
            ident += ch;
        }
        else {
            flushIdent();
        }
    }
    flushIdent();
    return { hasStructChild, hasTopLevelLeafLike, hasTopLevelDescription };
}
function parseKeyNamesFromBlock(block) {
    const out = [];
    const stmts = extractTopLevelStatements(block, 'key');
    for (const stmt of stmts) {
        const m = stmt.match(/^\s*key\s+("?)([^";]+)\1\s*;/m);
        if (!m)
            continue;
        const names = m[2].trim().split(/\s+/).filter(Boolean);
        out.push(...names);
    }
    return Array.from(new Set(out));
}
function collectTopLevelLeafLikeNames(block) {
    const out = [];
    const addNames = (keyword) => {
        const stmts = extractTopLevelStatements(block, keyword);
        for (const stmt of stmts) {
            const re = new RegExp(`^\\s*${keyword}\\s+([A-Za-z0-9_\\-]+)\\b`, 'm');
            const m = stmt.match(re);
            if (m)
                out.push(m[1]);
        }
    };
    addNames('leaf');
    addNames('leaf-list');
    addNames('rpc');
    addNames('notification');
    return out;
}
/**
 * shellRootMissingDescription:
 *   - For create-scope container/list:
 *     1. If the block:
 *        - Has structured child nodes at the top level (container/list/choice/uses, etc.)
 *        - And has no top-level leaf/leaf-list/rpc/notification
 *        -> treat it as a pure shell-root container/list.
 *     2. Such nodes must have a top-level description;
 *        if missing -> return true (violation, emit warning).
 */
/**
 * Detect shell-root containers/lists that lack a top-level description.
 * A shell root has structured children but no top-level leaf/leaf-list/rpc/notification.
 */
function shellRootMissingDescription(node, file) {
    if (!node || (node.kind !== 'container' && node.kind !== 'list')) {
        return false;
    }
    const block = extractBlockForNode(file, node);
    if (!block)
        return false;
    const info = analyzeShellBlock(block);
    if (node.kind === 'list') {
        const keyNames = parseKeyNamesFromBlock(block);
        const leafLikes = collectTopLevelLeafLikeNames(block);
        const nonKeyLeafLikes = leafLikes.filter((n) => !keyNames.includes(n));
        const isShellRoot = info.hasStructChild && nonKeyLeafLikes.length === 0;
        if (!isShellRoot)
            return false;
    }
    else {
        const isShellRoot = info.hasStructChild && !info.hasTopLevelLeafLike;
        if (!isShellRoot)
            return false;
    }
    return !info.hasTopLevelDescription;
}
/* ----------------- Export helpers ----------------- */
exports.coreHelpers = {
    moduleHeaderFieldsOkNode,
    moduleNameHasTelusPrefixNode,
    namespaceStartsWithTinaaNode,
    modulePrefixHasTelusPrefixNode,
    strictAugDevModuleNameBadNode,
    strictAugDevNamespaceBadNode,
    augDevPrefixNamingBad,
    constraintsBecameStricterForNode,
    modulePrefixChangedButRefsNotUpdatedNode,
    importPrefixChangedButRefsNotUpdated,
    hasDescriptionInBlock,
    mandatoryLeafNotUnderPresenceContainer,
    keyLeafDescriptionMissingWithin5Lines,
    newMandatoryNotGuarded,
    importBlockPrefixNotFirstOrMissing,
    stateToConfigMandatoryBad,
    materialChangeMissingRevisionRef,
    obsoleteDefinitionsRemovedNode,
    deviceNiContainerShouldUseOuterList,
    shellRootMissingDescription,
};
// Back-compat export name
exports.helpers = exports.coreHelpers;
//# sourceMappingURL=helpers.js.map
