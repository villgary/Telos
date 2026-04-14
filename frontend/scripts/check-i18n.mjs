/**
 * i18n completeness checker
 * Scans all TSX files for t('...') calls and verifies every key exists
 * in both zh-CN.json and en-US.json translation files.
 *
 * Usage: node scripts/check-i18n.mjs
 * Exit code 1 if any keys are missing.
 */
import { readFileSync, readdirSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PAGES_DIR = join(__dirname, '../src/pages')
const LOCALE_DIR = join(__dirname, '../src/locales')

// Extract all t('...') and t("...") keys from TSX content
function extractKeys(content) {
  const keys = new Set()
  // Match t('key') and t("key")
  const re = /t\(['"]([a-zA-Z0-9_.]+)['"]\)/g
  let m
  while ((m = re.exec(content)) !== null) {
    keys.add(m[1])
  }
  return keys
}

// Extract all keys from all TSX pages
function getUsedKeys() {
  const keys = new Set()
  for (const file of readdirSync(PAGES_DIR)) {
    if (!file.endsWith('.tsx')) continue
    const content = readFileSync(join(PAGES_DIR, file), 'utf8')
    for (const key of extractKeys(content)) {
      keys.add(key)
    }
  }
  return keys
}

function loadLocale(name) {
  const data = JSON.parse(readFileSync(join(LOCALE_DIR, name), 'utf8'))
  return new Set(Object.keys(data))
}

const used = getUsedKeys()
const zhKeys = loadLocale('zh-CN.json')
const enKeys = loadLocale('en-US.json')

const missingZh = [...used].filter(k => !zhKeys.has(k) && k !== 'a')
const missingEn = [...used].filter(k => !enKeys.has(k) && k !== 'a')

const green = (s) => `\x1b[32m${s}\x1b[0m`
const red = (s) => `\x1b[31m${s}\x1b[0m`
const yellow = (s) => `\x1b[33m${s}\x1b[0m`

let ok = true

if (missingZh.length > 0) {
  console.error(red(`✗ Missing ${missingZh.length} key(s) in zh-CN.json:`))
  missingZh.forEach(k => console.error(`  • ${k}`))
  ok = false
} else {
  console.log(green(`✓ zh-CN.json: all ${used.size} keys present`))
}

if (missingEn.length > 0) {
  console.error(red(`✗ Missing ${missingEn.length} key(s) in en-US.json:`))
  missingEn.forEach(k => console.error(`  • ${k}`))
  ok = false
} else {
  console.log(green(`✓ en-US.json: all ${used.size} keys present`))
}

// Also warn about unused keys (keys in locale but not used in code)
const unusedZh = [...zhKeys].filter(k => !used.has(k) && k !== 'a')
const unusedEn = [...enKeys].filter(k => !used.has(k) && k !== 'a')

if (unusedZh.length > 0) {
  console.log(yellow(`⚠ ${unusedZh.length} unused key(s) in zh-CN.json (may be intentionally reserved):`))
  unusedZh.slice(0, 10).forEach(k => console.log(`  • ${k}`))
  if (unusedZh.length > 10) console.log(`  ... and ${unusedZh.length - 10} more`)
}

if (!ok) {
  console.error('\nAdd missing keys to src/locales/zh-CN.json and src/locales/en-US.json')
  process.exit(1)
} else {
  console.log(`\n${green('✓ All i18n checks passed')}`)
  process.exit(0)
}
