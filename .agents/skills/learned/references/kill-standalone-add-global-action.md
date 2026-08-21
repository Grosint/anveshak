# Kill Standalone Page, Add Global Action

## Pattern
When a topic-scoped feature has a useless standalone page (requires pasting UUIDs,
empty without context), remove the standalone route and sidebar nav link. Keep the
embedded tab in TopicWorkspace. Add a global access point (search button, command
palette) in Layout sidebar for cross-topic discovery.

## When to use
A page that requires a topic_id to show anything useful should NOT be a standalone
route. It belongs as an embedded tab in TopicWorkspace. If the feature also needs
cross-topic access (search, convergence), add a global action in the sidebar instead
of a full page.

## Steps
1. Remove the `/feature` route from `App.tsx`
2. Remove the nav link from `primaryNav` in `Layout.tsx`
3. Keep the `<Feature embedded topicId={id} />` tab in TopicWorkspace (unchanged)
4. Add a sidebar button in Layout for global access (search modal, command palette)
5. Clean up unused icon components (TS will flag them)
6. Update Layout tests: assert nav link is GONE + new button EXISTS
7. Update page tests: test embedded mode only, remove standalone-specific tests

## Key details
- The `embedded` prop pattern already exists (`embedded-prop-page-reuse.md`)
- This pattern is about the ROUTING decision, not the component reuse
- The global action replaces the nav link — one sidebar slot for one slot
- If the feature needs cross-topic data, add a new backend endpoint scoped by org_id
  (not topic_id) — see `rules/multi-tenancy.md`

## Anti-pattern
Don't add a topic picker dropdown to the standalone page. If the user needs to pick
a topic first, they should be IN that topic's workspace already. A topic picker is
just TopicsDashboard with extra steps.

## Origin
Identifiers page required pasting raw UUID — no analyst would use it. Replaced with
IdentifierSearch modal (command palette style) accessible from sidebar. Embedded tab
in TopicWorkspace unchanged.
