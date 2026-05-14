import { execFileSync } from 'child_process'

type Command =
  | 'help'
  | 'status'
  | 'ready'
  | 'wait-checks'
  | 'failed-checks'
  | 'threads'
  | 'resolve-ai-threads'
  | 'resolve-all-threads'

type CliArgs = {
  command: Command
  pr: string | null
  timeoutMs: number
  pollMs: number
  includeHuman: boolean
}

type RepoRef = {
  owner: string
  repo: string
}

type PullRequestRef = RepoRef & {
  number: number
}

type RestPullRequest = {
  number: number
  html_url: string
  head: {
    ref: string
  }
}

type AuthenticatedUser = {
  login: string
}

type Author = {
  login: string
  __typename?: string
} | null

type ReviewComment = {
  author: Author
  body: string
  path: string | null
  line: number | null
  originalLine: number | null
  url: string
}

type ReviewThread = {
  id: string
  isResolved: boolean
  isOutdated: boolean
  comments: {
    nodes: ReviewComment[]
    pageInfo: {
      hasNextPage: boolean
    }
  }
}

type CheckRunContextNode = {
  __typename: 'CheckRun'
  name: string
  status: string
  conclusion: string | null
  detailsUrl: string | null
}

type StatusContextNode = {
  __typename: 'StatusContext'
  context: string
  state: string
  targetUrl: string | null
  description: string | null
}

type CheckContextNode = CheckRunContextNode | StatusContextNode

type PullRequestState = {
  id: string
  number: number
  title: string
  url: string
  isDraft: boolean
  mergedAt: string | null
  mergeable: string
  mergeStateStatus: string
  reviewDecision: string | null
  headRefName: string
  baseRefName: string
  reviewThreads: {
    nodes: ReviewThread[]
    pageInfo: {
      hasNextPage: boolean
    }
  }
  commits: {
    nodes: Array<{
      commit: {
        oid: string
        statusCheckRollup: {
          state: string
          contexts: {
            nodes: Array<CheckContextNode | null>
          }
        } | null
      }
    }>
  }
}

type GraphqlResponse<T> = {
  data?: T
  errors?: Array<{ message: string }>
}

type CheckSummary = {
  name: string
  state: 'pending' | 'success' | 'failure' | 'cancelled'
  url: string | null
  description: string | null
}

type ThreadClass = 'ai' | 'human' | 'mixed'

type ClassifiedThread = {
  thread: ReviewThread
  classification: ThreadClass
}

const restEndpoint = 'https://api.github.com'
const graphqlEndpoint = 'https://api.github.com/graphql'
const defaultTimeoutMs = 30 * 60 * 1000
const defaultPollMs = 15 * 1000
const noChecksGraceMs = 60 * 1000

const transientFetchMaxRetriesPerCycle = 8
const transientFetchBaseDelayMs = 1_000
const transientFetchMaxDelayMs = 30_000

const sleep = (ms: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, ms)
  })

const isTransientGithubRequestError = (error: unknown): boolean => {
  if (error instanceof AggregateError) {
    return error.errors.some((item) => isTransientGithubRequestError(item))
  }

  if (error instanceof TypeError) {
    return true
  }

  const message =
    error instanceof Error ? error.message : String(error).toLowerCase()

  if (message.includes('fetch failed')) {
    return true
  }

  if (
    /econnreset|etimedout|enotfound|eai_again|enetunreach|ehostunreach|socket/.test(
      message
    )
  ) {
    return true
  }

  if (/github (rest|graphql) (429|500|502|503|504|520)/i.test(message)) {
    return true
  }

  if (
    message.includes('github graphql errors:') &&
    /rate limit|throttl|secondary rate|too many requests|submitted too quickly/.test(
      message
    )
  ) {
    return true
  }

  return false
}

const defaultAiReviewerLogins = [
  'coderabbitai',
  'github-copilot',
  'copilot-pull-request-reviewer',
  'cursoragent',
  'cursor-agent',
]

const parseArgs = (): CliArgs => {
  const rawArgs = process.argv.slice(2)
  if (rawArgs.includes('--help') || rawArgs.includes('-h')) {
    return {
      command: 'help',
      pr: null,
      timeoutMs: defaultTimeoutMs,
      pollMs: defaultPollMs,
      includeHuman: false,
    }
  }

  const command = parseCommand(rawArgs[0])
  const args = command === rawArgs[0] ? rawArgs.slice(1) : rawArgs

  let pr: string | null = null
  let timeoutMs = defaultTimeoutMs
  let pollMs = defaultPollMs
  let includeHuman = false

  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    const next = args[i + 1]

    if (arg === '--pr' && next) {
      pr = next
      i++
      continue
    }

    if (arg === '--timeout-ms' && next) {
      timeoutMs = Number(next)
      i++
      continue
    }

    if (arg === '--poll-ms' && next) {
      pollMs = Number(next)
      i++
      continue
    }

    if (arg === '--include-human') {
      includeHuman = true
      continue
    }

    if (!arg.startsWith('--') && pr === null) {
      pr = arg
    }
  }

  return { command, pr, timeoutMs, pollMs, includeHuman }
}

const parseCommand = (value: string | undefined): Command => {
  const commands: Command[] = [
    'help',
    'status',
    'ready',
    'wait-checks',
    'failed-checks',
    'threads',
    'resolve-ai-threads',
    'resolve-all-threads',
  ]

  if (value && commands.includes(value as Command)) {
    return value as Command
  }

  return 'status'
}

const runGit = (args: string[]): string =>
  execFileSync('git', args, { encoding: 'utf-8' }).trim()

const getGithubToken = (): string => {
  if (process.env.GITHUB_TOKEN) {
    return process.env.GITHUB_TOKEN
  }

  try {
    return execFileSync('gh', ['auth', 'token'], {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()
  } catch {
    console.error('Missing GITHUB_TOKEN and `gh auth token` failed.')
    process.exit(1)
  }
}

const parseRemote = (): RepoRef => {
  let remoteUrl: string
  try {
    remoteUrl = runGit(['remote', 'get-url', 'origin'])
  } catch {
    console.error('Could not read git remote "origin".')
    process.exit(1)
  }

  const remoteMatch = remoteUrl.match(/[:/]([^/]+)\/([^/]+?)(?:\.git)?$/)
  if (!remoteMatch) {
    console.error(`Cannot parse owner/repo from remote: ${remoteUrl}`)
    process.exit(1)
  }

  return { owner: remoteMatch[1] ?? '', repo: remoteMatch[2] ?? '' }
}

const parsePrUrl = (value: string): PullRequestRef | null => {
  const match = value.match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/)
  if (!match) {
    return null
  }

  return {
    owner: match[1] ?? '',
    repo: match[2] ?? '',
    number: Number(match[3]),
  }
}

const githubRest = async <T>(
  token: string,
  path: string,
  init?: RequestInit
): Promise<T> => {
  const response = await fetch(`${restEndpoint}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const errorData = await response.text()
    throw new Error(`GitHub REST ${response.status}: ${errorData}`)
  }

  return (await response.json()) as T
}

const githubGraphql = async <T>(
  token: string,
  query: string,
  variables: Record<string, unknown>
): Promise<T> => {
  const response = await fetch(graphqlEndpoint, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query, variables }),
  })

  if (!response.ok) {
    throw new Error(`GitHub GraphQL ${response.status}`)
  }

  const result = (await response.json()) as GraphqlResponse<T>
  if (result.errors) {
    throw new Error(`GitHub GraphQL errors: ${JSON.stringify(result.errors)}`)
  }

  if (!result.data) {
    throw new Error('GitHub GraphQL returned no data')
  }

  return result.data
}

const getAuthenticatedUser = async (
  token: string
): Promise<AuthenticatedUser> =>
  githubRest<AuthenticatedUser>(token, '/user')

const findPullRequestForBranch = async ({
  token,
  repoRef,
  branch,
}: {
  token: string
  repoRef: RepoRef
  branch: string
}): Promise<PullRequestRef> => {
  const user = await getAuthenticatedUser(token)
  const heads = [
    `${repoRef.owner}:${branch}`,
    ...(user.login === repoRef.owner ? [] : [`${user.login}:${branch}`]),
  ]

  for (const head of heads) {
    const pullRequests = await githubRest<RestPullRequest[]>(
      token,
      `/repos/${repoRef.owner}/${repoRef.repo}/pulls?state=all&head=${encodeURIComponent(
        head
      )}&sort=updated&direction=desc&per_page=5`
    )

    const pullRequest = pullRequests[0]
    if (pullRequest) {
      return {
        owner: repoRef.owner,
        repo: repoRef.repo,
        number: pullRequest.number,
      }
    }
  }

  throw new Error(`No PR found for branch ${branch}`)
}

const resolvePullRequest = async ({
  token,
  pr,
}: {
  token: string
  pr: string | null
}): Promise<PullRequestRef> => {
  if (pr) {
    const prUrl = parsePrUrl(pr)
    if (prUrl) {
      return prUrl
    }

    if (/^\d+$/.test(pr)) {
      return { ...parseRemote(), number: Number(pr) }
    }
  }

  const branch = runGit(['branch', '--show-current'])
  if (!branch) {
    throw new Error('Cannot detect current branch')
  }

  return findPullRequestForBranch({
    token,
    repoRef: parseRemote(),
    branch,
  })
}

const fetchPullRequestState = async ({
  token,
  pullRequest,
}: {
  token: string
  pullRequest: PullRequestRef
}): Promise<PullRequestState> => {
  const data = await githubGraphql<{
    repository?: {
      pullRequest?: PullRequestState | null
    } | null
  }>(
    token,
    `
      query($owner: String!, $repo: String!, $prNumber: Int!) {
        repository(owner: $owner, name: $repo) {
          pullRequest(number: $prNumber) {
            id
            number
            title
            url
            isDraft
            mergedAt
            mergeable
            mergeStateStatus
            reviewDecision
            headRefName
            baseRefName
            reviewThreads(first: 100) {
              pageInfo {
                hasNextPage
              }
              nodes {
                id
                isResolved
                isOutdated
                comments(first: 50) {
                  pageInfo {
                    hasNextPage
                  }
                  nodes {
                    author {
                      login
                      __typename
                    }
                    body
                    path
                    line
                    originalLine
                    url
                  }
                }
              }
            }
            commits(last: 1) {
              nodes {
                commit {
                  oid
                  statusCheckRollup {
                    state
                    contexts(first: 100) {
                      nodes {
                        __typename
                        ... on CheckRun {
                          name
                          status
                          conclusion
                          detailsUrl
                        }
                        ... on StatusContext {
                          context
                          state
                          targetUrl
                          description
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    `,
    {
      owner: pullRequest.owner,
      repo: pullRequest.repo,
      prNumber: pullRequest.number,
    }
  )

  const state = data.repository?.pullRequest
  if (!state) {
    throw new Error(`Could not load PR #${pullRequest.number}`)
  }

  assertCompleteReviewThreadData(state)

  return state
}

const assertCompleteReviewThreadData = (pullRequest: PullRequestState) => {
  if (pullRequest.reviewThreads.pageInfo.hasNextPage) {
    throw new Error(
      'PR has more than 100 review threads. Refusing to classify or resolve partial thread data.'
    )
  }

  const hasThreadWithMoreComments = pullRequest.reviewThreads.nodes.some(
    (thread) => thread.comments.pageInfo.hasNextPage
  )
  if (hasThreadWithMoreComments) {
    throw new Error(
      'A review thread has more than 50 comments. Refusing to classify or resolve partial thread data.'
    )
  }
}

const normalizeCheckContexts = (
  pullRequest: PullRequestState
): CheckSummary[] => {
  const contexts =
    pullRequest.commits.nodes[0]?.commit.statusCheckRollup?.contexts.nodes ?? []
  const byName = new Map<string, CheckSummary>()
  const failureConclusions = new Set([
    'ACTION_REQUIRED',
    'FAILURE',
    'STARTUP_FAILURE',
    'TIMED_OUT',
  ])

  for (const context of contexts) {
    if (!context) {
      continue
    }

    if (context.__typename === 'CheckRun') {
      if (context.status !== 'COMPLETED') {
        byName.set(context.name, {
          name: context.name,
          state: 'pending',
          url: context.detailsUrl,
          description: context.status,
        })
        continue
      }

      const state = getCheckRunState(context.conclusion, failureConclusions)
      byName.set(context.name, {
        name: context.name,
        state,
        url: context.detailsUrl,
        description: context.conclusion,
      })
      continue
    }

    byName.set(context.context, {
      name: context.context,
      state: getStatusContextState(context.state),
      url: context.targetUrl,
      description: context.description,
    })
  }

  return Array.from(byName.values())
}

const getCheckRunState = (
  conclusion: string | null,
  failureConclusions: Set<string>
): CheckSummary['state'] => {
  if (conclusion === 'CANCELLED') {
    return 'cancelled'
  }

  if (failureConclusions.has(conclusion ?? '')) {
    return 'failure'
  }

  return 'success'
}

const getStatusContextState = (state: string): CheckSummary['state'] => {
  if (state === 'SUCCESS') {
    return 'success'
  }

  if (state === 'ERROR' || state === 'FAILURE') {
    return 'failure'
  }

  return 'pending'
}

const getAiReviewerLogins = (): Set<string> => {
  const configured = process.env.AI_REVIEW_BOTS?.split(',') ?? []
  return new Set(
    [...defaultAiReviewerLogins, ...configured]
      .map((login) => login.trim().toLowerCase())
      .filter(Boolean)
  )
}

const isAutomatedReviewer = (author: Author, aiReviewerLogins: Set<string>) => {
  if (!author) {
    return false
  }

  return (
    author.__typename === 'Bot' ||
    aiReviewerLogins.has(author.login.toLowerCase())
  )
}

const classifyThreads = (
  threads: ReviewThread[]
): ClassifiedThread[] => {
  const aiReviewerLogins = getAiReviewerLogins()

  return threads.map((thread) => {
    const authors = thread.comments.nodes.map((comment) => comment.author)
    const hasAutomatedAuthor = authors.some((author) =>
      isAutomatedReviewer(author, aiReviewerLogins)
    )
    const allAutomated =
      authors.length > 0 &&
      authors.every((author) => isAutomatedReviewer(author, aiReviewerLogins))

    let classification: ThreadClass = 'human'
    if (allAutomated) {
      classification = 'ai'
    } else if (hasAutomatedAuthor) {
      classification = 'mixed'
    }

    return { thread, classification }
  })
}

const getUnresolvedThreads = (pullRequest: PullRequestState) =>
  pullRequest.reviewThreads.nodes.filter((thread) => !thread.isResolved)

const getThreadCounts = (classifiedThreads: ClassifiedThread[]) => ({
  ai: classifiedThreads.filter((item) => item.classification === 'ai').length,
  human: classifiedThreads.filter((item) => item.classification === 'human')
    .length,
  mixed: classifiedThreads.filter((item) => item.classification === 'mixed')
    .length,
})

const printPullRequestHeader = (pullRequest: PullRequestState) => {
  console.log(`${pullRequest.title}`)
  console.log(`${pullRequest.url}`)
  console.log(
    `PR #${pullRequest.number} ${pullRequest.headRefName} -> ${pullRequest.baseRefName}`
  )
}

const printChecks = (checks: CheckSummary[]) => {
  if (checks.length === 0) {
    console.log('CHECKS total=0')
    return
  }

  for (const check of checks) {
    console.log(
      `CHECK ${check.state} ${check.name}${
        check.description ? ` (${check.description})` : ''
      }`
    )
    if (check.url) {
      console.log(`  ${check.url}`)
    }
  }
}

const printThreads = (classifiedThreads: ClassifiedThread[]) => {
  if (classifiedThreads.length === 0) {
    console.log('No unresolved review threads found.')
    return
  }

  for (const [index, item] of classifiedThreads.entries()) {
    const firstComment = item.thread.comments.nodes[0]
    const author = firstComment?.author?.login ?? 'unknown'
    const line = firstComment?.line ?? firstComment?.originalLine ?? '?'
    const path = firstComment?.path ?? 'unknown-path'
    const body = (firstComment?.body ?? '').replace(/\s+/g, ' ').trim()

    console.log(
      `THREAD ${index + 1} ${item.classification} by ${author} on ${path}:${line}${
        item.thread.isOutdated ? ' outdated=true' : ''
      }`
    )
    if (firstComment?.url) {
      console.log(`  ${firstComment.url}`)
    }
    if (body !== '') {
      console.log(`  ${body}`)
    }
  }
}

const printStatus = (pullRequest: PullRequestState) => {
  const checks = normalizeCheckContexts(pullRequest)
  const unresolvedThreads = getUnresolvedThreads(pullRequest)
  const classifiedThreads = classifyThreads(unresolvedThreads)
  const threadCounts = getThreadCounts(classifiedThreads)
  const failedChecks = checks.filter((check) => check.state === 'failure')
  const cancelledChecks = checks.filter((check) => check.state === 'cancelled')
  const pendingChecks = checks.filter((check) => check.state === 'pending')

  printPullRequestHeader(pullRequest)
  console.log(
    `STATE mergeable=${pullRequest.mergeable} mergeState=${pullRequest.mergeStateStatus} review=${pullRequest.reviewDecision ?? 'NONE'} draft=${pullRequest.isDraft}`
  )
  console.log(
    `CHECK_COUNTS total=${checks.length} pending=${pendingChecks.length} failed=${failedChecks.length} cancelled=${cancelledChecks.length}`
  )
  console.log(
    `THREAD_COUNTS total=${classifiedThreads.length} ai=${threadCounts.ai} human=${threadCounts.human} mixed=${threadCounts.mixed}`
  )
  printChecks(checks)
  printThreads(classifiedThreads)
}

const hasMergeBlocker = (pullRequest: PullRequestState) =>
  pullRequest.mergeable === 'CONFLICTING' ||
  pullRequest.mergeStateStatus === 'DIRTY' ||
  pullRequest.mergeStateStatus === 'BEHIND'

const isReady = (pullRequest: PullRequestState): boolean => {
  const checks = normalizeCheckContexts(pullRequest)
  const unresolvedThreads = getUnresolvedThreads(pullRequest)

  return (
    checks.every((check) => check.state === 'success') &&
    !hasMergeBlocker(pullRequest) &&
    pullRequest.reviewDecision !== 'CHANGES_REQUESTED' &&
    unresolvedThreads.length === 0
  )
}

const printFailedChecks = (pullRequest: PullRequestState) => {
  const checks = normalizeCheckContexts(pullRequest)
  const failedOrCancelled = checks.filter(
    (check) => check.state === 'failure' || check.state === 'cancelled'
  )

  if (failedOrCancelled.length === 0) {
    console.log('No failed checks found.')
    return
  }

  for (const check of failedOrCancelled) {
    console.log(
      `${check.state.toUpperCase()} ${check.name}${
        check.description ? ` (${check.description})` : ''
      }`
    )
    if (check.url) {
      console.log(check.url)
    }
  }
}

const fetchPullRequestStateWithTransientRetries = async ({
  token,
  pullRequest,
  deadlineMs,
}: {
  token: string
  pullRequest: PullRequestRef
  deadlineMs: number
}): Promise<PullRequestState | null> => {
  for (let attempt = 0; attempt < transientFetchMaxRetriesPerCycle; attempt++) {
    try {
      return await fetchPullRequestState({ token, pullRequest })
    } catch (error) {
      if (!isTransientGithubRequestError(error)) {
        throw error
      }

      const note = error instanceof Error ? error.message : String(error)
      const remainingMs = deadlineMs - Date.now()
      const isLastAttempt = attempt === transientFetchMaxRetriesPerCycle - 1

      if (isLastAttempt || remainingMs <= 0) {
        console.warn(
          `Transient GitHub error while polling checks (${note}); will retry after the poll interval.`
        )
        return null
      }

      const backoff = Math.min(
        transientFetchMaxDelayMs,
        transientFetchBaseDelayMs * 2 ** attempt
      )
      const delayMs = Math.min(backoff, Math.max(50, remainingMs - 1))

      console.warn(
        `Transient GitHub error while polling checks (${note}); retry ${attempt + 1}/${transientFetchMaxRetriesPerCycle} after ${Math.round(delayMs / 1000)}s`
      )
      await sleep(delayMs)
    }
  }

  return null
}

const waitForChecks = async ({
  token,
  pullRequest,
  timeoutMs,
  pollMs,
}: {
  token: string
  pullRequest: PullRequestRef
  timeoutMs: number
  pollMs: number
}): Promise<void> => {
  const startedAt = Date.now()
  let lastStatus = ''

  while (Date.now() - startedAt < timeoutMs) {
    const deadlineMs = startedAt + timeoutMs
    const state = await fetchPullRequestStateWithTransientRetries({
      token,
      pullRequest,
      deadlineMs,
    })

    if (!state) {
      if (Date.now() - startedAt >= timeoutMs) {
        console.error(
          `Timed out after ${Math.round(timeoutMs / 1000)}s waiting for checks.`
        )
        process.exit(3)
      }
      await sleep(pollMs)
      continue
    }

    const checks = normalizeCheckContexts(state)

    if (
      checks.length === 0 &&
      Date.now() - startedAt > noChecksGraceMs &&
      process.env.PR_WAIT_ALLOW_NO_CHECKS === 'true'
    ) {
      console.log('No checks found after grace period; treating as green.')
      return
    }

    if (checks.length === 0 && Date.now() - startedAt > noChecksGraceMs) {
      console.error(
        'No checks found after grace period. Set PR_WAIT_ALLOW_NO_CHECKS=true only for repos that intentionally have no CI.'
      )
      process.exit(3)
    }

    const failedChecks = checks.filter((check) => check.state === 'failure')
    const cancelledChecks = checks.filter((check) => check.state === 'cancelled')
    const pendingChecks = checks.filter((check) => check.state === 'pending')

    if (failedChecks.length > 0 || cancelledChecks.length > 0) {
      printPullRequestHeader(state)
      printFailedChecks(state)
      process.exit(2)
    }

    if (checks.length > 0 && pendingChecks.length === 0) {
      console.log(`Checks green for ${state.url}`)
      return
    }

    const nextStatus = `${checks.length - pendingChecks.length}/${checks.length} checks complete`
    if (nextStatus !== lastStatus) {
      console.log(nextStatus)
      lastStatus = nextStatus
    }

    await new Promise((resolve) => setTimeout(resolve, pollMs))
  }

  console.error(`Timed out after ${Math.round(timeoutMs / 1000)}s waiting for checks.`)
  process.exit(3)
}

const resolveReviewThread = async ({
  token,
  threadId,
}: {
  token: string
  threadId: string
}) => {
  const result = await githubGraphql<{
    resolveReviewThread?: {
      thread?: {
        isResolved: boolean
      } | null
    } | null
  }>(
    token,
    `
      mutation($threadId: ID!) {
        resolveReviewThread(input: { threadId: $threadId }) {
          thread {
            isResolved
          }
        }
      }
    `,
    { threadId }
  )

  if (!result.resolveReviewThread?.thread?.isResolved) {
    throw new Error(`Failed to resolve review thread ${threadId}`)
  }
}

const resolveThreads = async ({
  token,
  pullRequest,
  aiOnly,
  includeHuman,
}: {
  token: string
  pullRequest: PullRequestState
  aiOnly: boolean
  includeHuman: boolean
}) => {
  const unresolvedThreads = getUnresolvedThreads(pullRequest)
  const classifiedThreads = classifyThreads(unresolvedThreads)
  const humanOrMixedThreads = classifiedThreads.filter(
    (item) =>
      item.classification === 'human' || item.classification === 'mixed'
  )

  if (!aiOnly && humanOrMixedThreads.length > 0 && !includeHuman) {
    const counts = getThreadCounts(classifiedThreads)
    console.error(
      `Refusing to resolve human/mixed threads without --include-human. human=${counts.human} mixed=${counts.mixed}`
    )
    console.error(
      'Inspect and address human/mixed threads first, then rerun with --include-human.'
    )
    process.exit(4)
  }

  const threadsToResolve = aiOnly
    ? classifiedThreads.filter((item) => item.classification === 'ai')
    : classifiedThreads

  if (threadsToResolve.length === 0) {
    console.log('No matching unresolved threads to resolve.')
    return
  }

  for (const item of threadsToResolve) {
    await resolveReviewThread({ token, threadId: item.thread.id })
    console.log(`Resolved ${item.classification} thread ${item.thread.id}`)
  }

  console.log(`Resolved ${threadsToResolve.length} thread(s).`)
}

const run = async () => {
  const args = parseArgs()

  if (args.command === 'help') {
    printUsage()
    return
  }

  const token = getGithubToken()
  const pullRequest = await resolvePullRequest({ token, pr: args.pr })

  if (args.command === 'wait-checks') {
    await waitForChecks({
      token,
      pullRequest,
      timeoutMs: args.timeoutMs,
      pollMs: args.pollMs,
    })
    return
  }

  const state = await fetchPullRequestState({ token, pullRequest })

  if (args.command === 'status') {
    printStatus(state)
    return
  }

  if (args.command === 'ready') {
    printStatus(state)
    process.exit(isReady(state) ? 0 : 1)
  }

  if (args.command === 'failed-checks') {
    printFailedChecks(state)
    return
  }

  if (args.command === 'threads') {
    printPullRequestHeader(state)
    printThreads(classifyThreads(getUnresolvedThreads(state)))
    return
  }

  if (args.command === 'resolve-ai-threads') {
    await resolveThreads({
      token,
      pullRequest: state,
      aiOnly: true,
      includeHuman: false,
    })
    return
  }

  if (args.command === 'resolve-all-threads') {
    await resolveThreads({
      token,
      pullRequest: state,
      aiOnly: false,
      includeHuman: args.includeHuman,
    })
  }
}

const printUsage = () => {
  console.log(`Usage:
  npx tsx ~/.cursor/scripts/github-pr.ts status [--pr <number-or-url>]
  npx tsx ~/.cursor/scripts/github-pr.ts ready [--pr <number-or-url>]
  npx tsx ~/.cursor/scripts/github-pr.ts wait-checks [--pr <number-or-url>] [--timeout-ms <ms>] [--poll-ms <ms>]
  npx tsx ~/.cursor/scripts/github-pr.ts failed-checks [--pr <number-or-url>]
  npx tsx ~/.cursor/scripts/github-pr.ts threads [--pr <number-or-url>]
  npx tsx ~/.cursor/scripts/github-pr.ts resolve-ai-threads [--pr <number-or-url>]
  npx tsx ~/.cursor/scripts/github-pr.ts resolve-all-threads [--pr <number-or-url>] [--include-human]
`)
}

run().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
