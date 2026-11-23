// Offline sanity lint of firestore.rules (there is no rules compiler without the emulator / Java).  It catches the typical hand-editing mistakes:
// unbalanced braces / parentheses / brackets / quotes, a missing `rules_version` or `service`, a function body statement without `;`, an `allow` without a
// condition, methods and functions that do not exist in the rules language (e.g. `request.resource.size()`), and calls of undefined helper functions.
// It does NOT prove the rules compile or behave: that is what rules.test.mjs does against the emulator.
//   node lint-rules.mjs ../firestore.rules        (exit code 1 on any problem)
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const KNOWN_METHODS = new Set(["keys", "hasOnly", "hasAll", "hasAny", "size", "matches", "get", "data", "diff", "affectedKeys", "toSet", "join", "hasOnly", "concat", "keys", "values", "split", "lower", "upper", "trim", "replace", "debug", "path", "exists", "existsAfter", "get", "getAfter"]);
const KNOWN_GLOBAL_FUNCTIONS = new Set(["get", "getAfter", "exists", "existsAfter", "debug", "path", "string", "int", "float", "bool", "bytes", "duration", "timestamp", "latlng", "math", "hashing", "request", "resource"]);
const ALLOWED_OPS = new Set(["read", "write", "get", "list", "create", "update", "delete"]);

export function stripComments(src) {
  let out = "";
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (c === "'" || c === '"') {
      const q = c;
      let j = i + 1;
      while (j < src.length && src[j] !== q) {
        if (src[j] === "\\") j++;
        j++;
      }
      out += src.slice(i, j + 1);
      i = j;
    } else if (c === "/" && src[i + 1] === "/") {
      while (i < src.length && src[i] !== "\n") i++;
      out += "\n";
    } else if (c === "/" && src[i + 1] === "*") {
      const end = src.indexOf("*/", i + 2);
      i = end < 0 ? src.length : end + 1;
    } else out += c;
  }
  return out;
}

export function lintRules(source) {
  const problems = [];
  const text = stripComments(source);
  const lineOf = (idx) => text.slice(0, idx).split("\n").length;

  if (!/^\s*rules_version\s*=\s*'2'\s*;/.test(text)) problems.push("missing `rules_version = '2';` at the top");
  if (!/service\s+cloud\.firestore\s*\{/.test(text)) problems.push("missing `service cloud.firestore {`");
  if (!/match\s+\/databases\/\{database\}\/documents\s*\{/.test(text)) problems.push("missing `match /databases/{database}/documents {`");

  // balance + quotes
  const stack = [];
  const pairs = { ")": "(", "]": "[", "}": "{" };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "'" || c === '"') {
      let j = i + 1;
      while (j < text.length && text[j] !== c && text[j] !== "\n") {
        if (text[j] === "\\") j++;
        j++;
      }
      if (text[j] !== c) {
        problems.push(`line ${lineOf(i)}: unterminated string`);
        break;
      }
      i = j;
    } else if ("([{".includes(c)) stack.push([c, i]);
    else if (")]}".includes(c)) {
      const top = stack.pop();
      if (!top || top[0] !== pairs[c]) {
        problems.push(`line ${lineOf(i)}: unbalanced '${c}'`);
        break;
      }
    }
  }
  for (const [c, i] of stack) problems.push(`line ${lineOf(i)}: '${c}' is never closed`);

  // function bodies: every statement ends with ';'
  const fnRe = /function\s+(\w+)\s*\(([^)]*)\)\s*\{/g;
  const defined = new Set();
  let m;
  while ((m = fnRe.exec(text))) {
    defined.add(m[1]);
    let depth = 1;
    let i = fnRe.lastIndex;
    const start = i;
    while (i < text.length && depth) {
      if (text[i] === "{") depth++;
      else if (text[i] === "}") depth--;
      i++;
    }
    const body = text.slice(start, i - 1).trim();
    if (!/\breturn\b/.test(body)) problems.push(`line ${lineOf(m.index)}: function ${m[1]} has no return`);
    if (!body.endsWith(";")) problems.push(`line ${lineOf(m.index)}: function ${m[1]}: the last statement does not end with ';'`);
    for (const stmt of body.split(";").map((s) => s.trim()).filter(Boolean)) {
      if (!/^(let\s+\w+\s*=|return\b)/.test(stmt)) problems.push(`line ${lineOf(m.index)}: function ${m[1]}: statement does not start with let / return: "${stmt.slice(0, 40)}"`);
      else if (/(?:^|\W)(let\s+\w+\s*=|return\b)/.test(stmt.slice(3))) problems.push(`line ${lineOf(m.index)}: function ${m[1]}: two statements without ';' between them: "${stmt.slice(0, 40)}"`);
    }
  }

  // allow statements
  const allowRe = /allow\s+([\w\s,]+?)\s*(:\s*if\s*([\s\S]*?))?;/g;
  let nAllow = 0;
  while ((m = allowRe.exec(text))) {
    nAllow++;
    for (const op of m[1].split(",").map((s) => s.trim())) if (!ALLOWED_OPS.has(op)) problems.push(`line ${lineOf(m.index)}: unknown operation '${op}'`);
    if (!m[2]) problems.push(`line ${lineOf(m.index)}: allow without ': if <condition>'`);
    else if (!m[3].trim()) problems.push(`line ${lineOf(m.index)}: empty condition`);
  }
  if (!nAllow) problems.push("no allow statement at all");
  if (/allow[^;]*:\s*if\s*true\s*;/.test(text)) problems.push("an `allow ... if true` rule opens the data to everyone");

  // method calls: `.name(` must exist in the language; the classic mistake is a document byte size
  const callRe = /\.(\w+)\s*\(/g;
  while ((m = callRe.exec(text))) {
    if (!KNOWN_METHODS.has(m[1])) problems.push(`line ${lineOf(m.index)}: unknown method .${m[1]}()`);
  }
  if (/request\.resource\.size\s*\(/.test(text) || /\bresource\.size\s*\(/.test(text)) problems.push("`resource.size()` does not exist (there is no byte size of a document): bound the fields instead");

  // helper functions used must be defined
  const useRe = /(?<![.\w])(\w+)\s*\(/g;
  while ((m = useRe.exec(text))) {
    const name = m[1];
    if (["function", "allow", "match", "if", "let", "return", "service"].includes(name)) continue;
    if (!defined.has(name) && !KNOWN_GLOBAL_FUNCTIONS.has(name)) problems.push(`line ${lineOf(m.index)}: call of undefined function ${name}()`);
  }

  // every path the app uses must be matched
  for (const frag of ["/users/{uid}", "/profiles/{profileId}", "/settings/{docId}"]) if (!text.includes(`match ${frag}`)) problems.push(`no match block for ${frag}`);
  return problems;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const file = process.argv[2] ?? "../firestore.rules";
  const problems = lintRules(readFileSync(file, "utf8"));
  if (problems.length) {
    console.error(`${file}: ${problems.length} problem(s)`);
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log(`${file}: lint ok (this is a sanity check only; run npm run test:emulator for the real thing)`);
}
