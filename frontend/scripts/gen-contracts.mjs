// Compiles every schema in ../contracts/schemas into one src/contracts/generated.ts.
//
// json-schema-to-typescript does not understand draft 2020-12 `prefixItems` or `if`/`then`, and would try to
// fetch `$id` URLs over the network, so the schemas are first bundled into a single root document whose
// `$defs` hold every named type and whose `$ref`s are all local.
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript'

const here = dirname(fileURLToPath(import.meta.url))
const schemasDir = resolve(here, '../../contracts/schemas')
const outFile = resolve(here, '../src/contracts/generated.ts')

const BANNER = `/* eslint-disable */
/**
 * GENERATED — do not edit.
 * Source: contracts/schemas/*.schema.json. Regenerate with \`npm run contracts:gen\` (or \`make contracts\`).
 */`

const files = readdirSync(schemasDir)
  .filter((f) => f.endsWith('.schema.json'))
  .sort()
const docs = new Map(files.map((f) => [f, JSON.parse(readFileSync(join(schemasDir, f), 'utf8'))]))

/** File name → name of its root type (only for files whose root is itself a type). */
const rootNames = new Map()
for (const [file, doc] of docs) {
  if (doc.type !== undefined || doc.properties !== undefined) rootNames.set(file, doc.title)
}

function localRef(ref, file) {
  const [target, fragment] = ref.split('#')
  if (target === '') return `#${fragment}`
  const targetFile = target.split('/').pop()
  if (!docs.has(targetFile)) throw new Error(`${file}: unknown $ref target ${ref}`)
  if (fragment) return `#${fragment}`
  const name = rootNames.get(targetFile)
  if (!name) throw new Error(`${file}: $ref to a schema without a root type: ${ref}`)
  return `#/$defs/${name}`
}

function conditionalTag(entry) {
  const props = entry?.if?.properties
  if (!props || entry.else !== undefined || !entry.then) return undefined
  const keys = Object.keys(props)
  if (keys.length !== 1 || props[keys[0]].const === undefined) return undefined
  return { key: keys[0], value: props[keys[0]].const }
}

/** `allOf: [{if: {properties: {type: {const: X}}}, then: {properties: {payload: …}}}, …]` → `oneOf` variants. */
function discriminatedVariants(schema) {
  const tags = (schema.allOf ?? []).map(conditionalTag)
  if (tags.length === 0 || tags.some((t) => !t || t.key !== tags[0].key)) return undefined
  const key = tags[0].key
  const values = schema.properties?.[key]?.enum
  if (!values) return undefined
  const { allOf, title, description, ...base } = schema
  const variants = allOf.map((entry, i) => ({
    ...base,
    properties: { ...base.properties, [key]: { const: tags[i].value }, ...entry.then.properties },
  }))
  const rest = values.filter((v) => !tags.some((t) => t.value === v))
  if (rest.length > 0) variants.push({ ...base, properties: { ...base.properties, [key]: { enum: rest } } })
  return { title, description, oneOf: variants }
}

function transform(node, file) {
  if (Array.isArray(node)) return node.map((n) => transform(n, file))
  if (node === null || typeof node !== 'object') return node

  const variants = discriminatedVariants(node)
  if (variants) return transform(variants, file)

  const out = {}
  for (const [key, value] of Object.entries(node)) {
    if (['$schema', '$id', 'if', 'then', 'else', 'not'].includes(key)) continue
    if (key === '$ref') out.$ref = localRef(value, file)
    else if (key === 'prefixItems') {
      out.items = transform(value, file)
      out.additionalItems = false
    } else if (key === 'allOf') {
      const kept = value.filter((entry) => !conditionalTag(entry) && entry.if === undefined)
      if (kept.length > 0) out.allOf = transform(kept, file)
    } else if (key === '$defs' || key === 'properties') {
      out[key] = Object.fromEntries(Object.entries(value).map(([k, v]) => [k, transform(v, file)]))
    } else out[key] = transform(value, file)
  }
  if (out.type === 'object' && out.properties === undefined && out.additionalProperties === undefined) {
    out.additionalProperties = true
  }
  return out
}

const defs = {}
function addDef(name, schema, file) {
  if (Object.hasOwn(defs, name)) throw new Error(`${file}: duplicate type name ${name}`)
  defs[name] = schema
}
for (const [file, doc] of docs) {
  const { $defs, ...root } = doc
  for (const [name, schema] of Object.entries($defs ?? {})) addDef(name, transform(schema, file), file)
  if (rootNames.has(file)) addDef(rootNames.get(file), transform({ ...root }, file), file)
}

const bundle = {
  title: 'TactiStreamContracts',
  description: 'Every named contract type; see contracts/schemas.',
  type: 'object',
  additionalProperties: false,
  properties: Object.fromEntries(Object.keys(defs).map((name) => [name, { $ref: `#/$defs/${name}` }])),
  $defs: defs,
}

const ts = await compile(bundle, 'TactiStreamContracts', {
  bannerComment: BANNER,
  additionalProperties: false,
  unreachableDefinitions: true,
  unknownAny: true,
  ignoreMinAndMaxItems: true,
  cwd: schemasDir,
  $refOptions: { resolve: { http: false, file: false } },
  style: { semi: false, singleQuote: true, trailingComma: 'all', printWidth: 110 },
})

mkdirSync(dirname(outFile), { recursive: true })
writeFileSync(outFile, ts)
console.log(`wrote ${outFile} (${Object.keys(defs).length} types from ${files.length} schemas)`)
