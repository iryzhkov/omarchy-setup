# Issue tracker

This repo's issue tracker is **GitHub Issues** on `iryzhkov/omarchy-setup`, reached with the `gh` CLI
(already authenticated). Sub-issues and issue dependencies are **native** GitHub features here;
never fall back to a body convention for them.

Handy shell setup for the snippets below:

```bash
REPO=iryzhkov/omarchy-setup
gh() { command gh "$@" --repo "$REPO"; }   # or pass -R $REPO / --repo $REPO explicitly
```

`gh issue` has no first-class subcommands for sub-issues or dependencies, so those go through
`gh api graphql`. Every mutation below is verified against the live schema.

## Resolving a reference

A bare `#42` means issue-or-PR 42 in `iryzhkov/omarchy-setup`. Resolve it with:

```bash
gh issue view 42 --json number,title,state,body,labels,assignees,url,comments
gh pr   view 42 --json number,title,state,body,labels,author,url,comments,files   # if it is a PR
```

`gh issue view` on a PR number fails; try `gh pr view` when it does. Full URLs are also valid
references, including to other repos — read those with `gh issue view <url>`.

## Label vocabulary

The canonical role names in the skills map 1:1 onto these label strings:

| Canonical role    | Label in this repo |
| ----------------- | ------------------ |
| `bug`             | `bug`              |
| `enhancement`     | `enhancement`      |
| `needs-triage`    | `needs-triage`     |
| `needs-info`      | `needs-info`       |
| `ready-for-agent` | `ready-for-agent`  |
| `ready-for-human` | `ready-for-human`  |
| `wontfix`         | `wontfix`          |

Wayfinder adds `wayfinder:map` and the ticket types `wayfinder:research`, `wayfinder:prototype`,
`wayfinder:grilling`, `wayfinder:task`.

```bash
gh issue edit 42 --add-label ready-for-agent --remove-label needs-triage
gh issue list --label needs-triage --state open --json number,title,createdAt,url
```

## External pull requests

External = a PR whose author is **not** the repo owner and not in the `write`-permission set.
Check with `gh pr view <n> --json author,authorAssociation`; `OWNER`, `MEMBER` and `COLLABORATOR`
count as internal, `CONTRIBUTOR`/`FIRST_TIME_CONTRIBUTOR`/`NONE` as external. Triage discovery
surfaces only external PRs; an explicitly named PR is always in scope.

## Wayfinding operations

Vocabulary for this tracker:

| Wayfinder concept | GitHub expression                                  |
| ----------------- | -------------------------------------------------- |
| the map           | an issue labelled `wayfinder:map`                   |
| a ticket          | a **sub-issue** of the map issue                    |
| blocking          | the native **issue dependency** (`blockedBy`)       |
| a claim           | the **assignee** (an open, unassigned ticket is unclaimed) |
| resolution        | a comment, then close the issue                     |

Mutations take **node IDs**, not issue numbers. Get one with:

```bash
gh issue view <number> --json id --jq .id
```

### Create the map

```bash
gh issue create --title "<destination name>" --label wayfinder:map --body-file map.md
```

### Create a ticket and attach it to the map

Create first, then wire — issues need ids before they can reference each other.

```bash
TICKET=$(gh issue create --title "<question>" --label wayfinder:grilling --body-file ticket.md)
TICKET_ID=$(gh issue view "$TICKET" --json id --jq .id)
MAP_ID=$(gh issue view <map-number> --json id --jq .id)

gh api graphql -f query='
  mutation($parent:ID!, $child:ID!) {
    addSubIssue(input:{issueId:$parent, subIssueId:$child}) { subIssue { number title } }
  }' -f parent="$MAP_ID" -f child="$TICKET_ID"
```

### Wire a blocking edge

`addBlockedBy(issueId: X, blockingIssueId: Y)` reads as "**X is blocked by Y**".

```bash
gh api graphql -f query='
  mutation($issue:ID!, $blocker:ID!) {
    addBlockedBy(input:{issueId:$issue, blockingIssueId:$blocker}) { issue { number } }
  }' -f issue="$TICKET_ID" -f blocker="$BLOCKER_ID"
```

Use `removeBlockedBy` with the same inputs to unwire one.

### The frontier query

The frontier is every child of the map that is **open**, **unassigned**, and has **no open
blocker**. `subIssues` and `blockedBy` take no state filter, so filter client-side:

```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $map:Int!) {
    repository(owner:$owner, name:$repo) {
      issue(number:$map) {
        subIssues(first:100) {
          nodes {
            number title url state
            assignees(first:5) { totalCount }
            labels(first:10) { nodes { name } }
            blockedBy(first:50) { nodes { number state } }
          }
        }
      }
    }
  }' -f owner=iryzhkov -f repo=omarchy-setup -F map=<map-number> --jq '
    .data.repository.issue.subIssues.nodes[]
    | select(.state == "OPEN")
    | select(.assignees.totalCount == 0)
    | select([.blockedBy.nodes[] | select(.state == "OPEN")] | length == 0)
    | "#\(.number) \(.title) — \(.url)"'
```

Drop the `assignees` filter to see the whole open frontier including claimed tickets; drop the
`blockedBy` filter to see everything still outstanding.

`issueDependenciesSummary { totalBlockedBy totalBlocking }` gives the counts cheaply when you only
need to know whether a ticket is blocked at all.

### Claim a ticket

Before any work, so concurrent sessions skip it:

```bash
gh issue edit <number> --add-assignee @me
```

### Resolve a ticket

```bash
gh issue comment <number> --body-file answer.md
gh issue close <number>
```

Then append the one-line gist plus link to the map's **Decisions so far**:

```bash
gh issue view <map-number> --json body --jq .body > map.md
# edit map.md
gh issue edit <map-number> --body-file map.md
```

### Rule a ticket out of scope

Close it (a closed ticket is unambiguously off the frontier), leave the reason on the map's
**Out of scope** section, and do **not** list it under Decisions so far:

```bash
gh issue close <number> --reason "not planned" --comment "Out of scope: <why>"
```
