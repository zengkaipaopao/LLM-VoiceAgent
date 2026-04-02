import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, '..');
const localesRoot = path.join(projectRoot, 'public', 'locales');
const srcRoot = path.join(projectRoot, 'src');
const BASE_LOCALE = 'zh-CN';

const SUPPORTED_NAMESPACES = new Set(['common', 'pages', 'navigation']);

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    throw new Error(`Failed to parse JSON: ${filePath}\n${String(error)}`);
  }
}

function flattenKeys(value, prefix = '', output = new Set()) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    if (prefix) {
      output.add(prefix);
    }
    return output;
  }

  for (const [key, nextValue] of Object.entries(value)) {
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    if (nextValue && typeof nextValue === 'object' && !Array.isArray(nextValue)) {
      flattenKeys(nextValue, nextPrefix, output);
    } else {
      output.add(nextPrefix);
    }
  }

  return output;
}

function hasPath(source, keyPath) {
  const parts = keyPath.split('.');
  let cursor = source;

  for (const part of parts) {
    if (!cursor || typeof cursor !== 'object' || !(part in cursor)) {
      return false;
    }
    cursor = cursor[part];
  }

  return true;
}

function walkFiles(directory, predicate, output = []) {
  const entries = fs.readdirSync(directory, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith('.')) {
      continue;
    }

    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') {
        continue;
      }
      walkFiles(fullPath, predicate, output);
    } else if (predicate(fullPath)) {
      output.push(fullPath);
    }
  }
  return output;
}

function parseLiteralKey(literal) {
  if (!literal) {
    return null;
  }
  if (literal.includes('${')) {
    return null;
  }

  if (literal.includes(':')) {
    const [namespace, ...rest] = literal.split(':');
    if (!SUPPORTED_NAMESPACES.has(namespace)) {
      return null;
    }
    const keyPath = rest.join(':').trim();
    return keyPath ? { namespace, keyPath } : null;
  }

  for (const namespace of SUPPORTED_NAMESPACES) {
    const prefix = `${namespace}.`;
    if (literal.startsWith(prefix)) {
      return {
        namespace,
        keyPath: literal.slice(prefix.length),
      };
    }
  }

  return null;
}

const localeDirs = fs
  .readdirSync(localesRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();

if (!localeDirs.includes(BASE_LOCALE)) {
  throw new Error(`Base locale "${BASE_LOCALE}" not found in ${localesRoot}`);
}

const baseNamespaceFiles = fs
  .readdirSync(path.join(localesRoot, BASE_LOCALE))
  .filter((fileName) => fileName.endsWith('.json'))
  .sort();

const localeData = {};
for (const locale of localeDirs) {
  localeData[locale] = {};
  for (const namespaceFile of baseNamespaceFiles) {
    const namespace = namespaceFile.replace(/\.json$/, '');
    const filePath = path.join(localesRoot, locale, namespaceFile);
    if (!fs.existsSync(filePath)) {
      localeData[locale][namespace] = null;
      continue;
    }
    localeData[locale][namespace] = readJson(filePath);
  }
}

const parityIssues = [];
for (const namespaceFile of baseNamespaceFiles) {
  const namespace = namespaceFile.replace(/\.json$/, '');
  const baseObject = localeData[BASE_LOCALE][namespace];
  const baseKeys = flattenKeys(baseObject);

  for (const locale of localeDirs) {
    const namespaceObject = localeData[locale][namespace];
    if (!namespaceObject) {
      parityIssues.push(`[${locale}] Missing namespace file: ${namespaceFile}`);
      continue;
    }

    for (const keyPath of baseKeys) {
      if (!hasPath(namespaceObject, keyPath)) {
        parityIssues.push(`[${locale}] ${namespace}:${keyPath}`);
      }
    }
  }
}

const sourceFiles = walkFiles(srcRoot, (filePath) => /\.(ts|tsx|js|jsx)$/.test(filePath));
const keyPattern = /\b(?:i18n\.t|t)\(\s*(['"`])([^'"`]+)\1/g;
const sourceKeySet = new Map();

for (const filePath of sourceFiles) {
  const raw = fs.readFileSync(filePath, 'utf8');
  let match;
  while ((match = keyPattern.exec(raw)) !== null) {
    const parsed = parseLiteralKey(match[2]);
    if (!parsed) {
      continue;
    }
    const baseNamespaceObject = localeData[BASE_LOCALE]?.[parsed.namespace];
    if (!baseNamespaceObject || !hasPath(baseNamespaceObject, parsed.keyPath)) {
      continue;
    }
    const mapKey = `${parsed.namespace}:${parsed.keyPath}`;
    if (!sourceKeySet.has(mapKey)) {
      sourceKeySet.set(mapKey, { ...parsed, filePath });
    }
  }
}

const sourceIssues = [];
for (const keyInfo of sourceKeySet.values()) {
  for (const locale of localeDirs) {
    const namespaceObject = localeData[locale][keyInfo.namespace];
    if (!namespaceObject || !hasPath(namespaceObject, keyInfo.keyPath)) {
      sourceIssues.push(
        `[${locale}] missing ${keyInfo.namespace}:${keyInfo.keyPath} (used in ${path.relative(
          projectRoot,
          keyInfo.filePath
        )})`
      );
    }
  }
}

if (parityIssues.length > 0 || sourceIssues.length > 0) {
  console.error('\n[i18n] Translation check failed.');

  if (parityIssues.length > 0) {
    console.error('\n[i18n] Locale parity issues (compared with zh-CN):');
    for (const issue of parityIssues.sort()) {
      console.error(`- ${issue}`);
    }
  }

  if (sourceIssues.length > 0) {
    console.error('\n[i18n] Missing keys referenced in source:');
    for (const issue of sourceIssues.sort()) {
      console.error(`- ${issue}`);
    }
  }

  process.exit(1);
}

console.log(
  `[i18n] OK. Checked ${sourceKeySet.size} referenced keys across ${localeDirs.length} locales.`
);
