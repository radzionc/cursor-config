import { execFileSync } from 'child_process'
import { homedir } from 'os'
import { join } from 'path'

const pr = process.argv[2]
const isListMode = process.argv.includes('--list')
const isAiOnlyMode = process.argv.includes('--ai-only')
const includeHuman = process.argv.includes('--include-human')

if (!pr) {
  console.error(
    'Usage: npx tsx resolve-pr-comments.ts <PR_NUMBER_OR_URL> [--list] [--ai-only] [--include-human]'
  )
  process.exit(1)
}

if (!isListMode && !isAiOnlyMode && !includeHuman) {
  console.error(
    'Refusing to resolve human/mixed threads without --include-human. List and address threads first.'
  )
  process.exit(4)
}

let command = 'resolve-all-threads'
if (isListMode) {
  command = 'threads'
} else if (isAiOnlyMode) {
  command = 'resolve-ai-threads'
}

const scriptPath = join(
  homedir(),
  '.cursor',
  'scripts',
  'github-pr.ts'
)

const args = ['tsx', scriptPath, command, '--pr', pr]
if (includeHuman) {
  args.push('--include-human')
}

execFileSync('npx', args, {
  stdio: 'inherit',
})
