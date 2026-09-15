# What Defeats `React.memo`

`memo(Child)` skips a re-render only when **every prop is identical by reference**
(`Object.is`) to the previous render. Value equality is irrelevant. Everything
below is a way to hand a child a fresh reference for unchanged data.

This matters most on a high-frequency update path (streaming tokens, keystrokes,
websocket messages), because there the parent re-renders many times per second
and every memo miss multiplies by the number of children on screen.

## The catalog

| Defeater | Why it happens | Fix |
|---|---|---|
| Inline arrow/object/array in JSX | New reference every render | Hoist, `useCallback`, `useMemo`, or a module constant |
| `useCallback` with a per-event value in deps | Deps change → callback identity changes | Read the value from a ref; drop the dep |
| `useMemo` whose dep is a rebuilt array | Upstream rebuilds the array each dispatch | Cache on stable identity, or depend on a narrower value |
| Array/object **container** rebuilt around stable items | `memo` compares the container, not its elements | Cache and reuse the container itself |
| Context value object rebuilt each render | Every consumer re-renders regardless of memo | Split contexts by volatility; `useMemo` the value |
| `.map()` projection in render | New objects per pass | `WeakMap` keyed by the source object |
| Spreading to add a derived field (`{...msg, x}`) | New object even when `msg` is unchanged | `WeakMap` cache keyed by `msg` |
| Non-primitive default prop (`= []`, `= {}`) | Fresh literal per render | Module-level frozen constant |
| Children passed as elements | New element objects each render | Memoize the subtree or lift it |

## Two real cases

Both from a React chat UI that streamed agent responses. `memo()` was already on
both children, message objects upstream were already identity-stable by design,
and the page still re-rendered **every message on screen for every token**:
102 `MessageItem` + 50 `ThinkingBlock` renders per token at 50 turns of history.

### 1. A callback holding the live array

```tsx
// BEFORE — `messages` is a new array on every reducer dispatch (~10x/s while
// streaming), so this callback is new every token, and it is a prop of EVERY
// MessageItem on screen.
const handleRegenerate = useCallback(() => {
  const lastUser = findLastUserMessage(messages);
  ...
}, [messages, sendMessage, toast]);

// AFTER — read through a ref; identity is now stable across frames.
const messagesRef = useRef(messages);
messagesRef.current = messages;              // assign during render, not in an effect

const handleRegenerate = useCallback(() => {
  const lastUser = findLastUserMessage(messagesRef.current);
  ...
}, [sendMessage, toast]);
```

Result on its own: 102 → 2 renders per token.

The ref assignment belongs in the render body when the handler is only invoked
from events — an effect would lag by one render. Do not use this pattern when the
value must trigger a re-render; it deliberately does not.

### 2. A container rebuilt around stable contents

The codebase had already done the hard part: a `WeakMap` cached the per-message
projection so each element kept its identity. But the **array holding them** was
rebuilt on every recompute, and that array was the prop:

```tsx
// BEFORE — elements stable, container not. memo compares the container.
groups.push({
  type: 'thinking',
  messages: toThinkingMessages(block),   // new array every time
  turnKey,
});
```

Fix: cache the whole group object, keyed by a stable identifier, and reuse it
while its source items are elementwise identical.

```tsx
const cacheRef = useRef(new Map<string, { src: Msg[]; group: Group }>());

const push = (src: Msg[], turnKey: string) => {
  // one key can legitimately open more than one block — disambiguate with an ordinal
  const key = `${turnKey}#${ordinal}`;
  liveKeys.add(key);

  const hit = cacheRef.current.get(key);
  if (hit && hit.src.length === src.length && hit.src.every((m, i) => m === src[i])) {
    groups.push(hit.group);              // same object -> memo bails
    return;
  }
  const group = { type: 'thinking', messages: toThinkingMessages(src), turnKey };
  cacheRef.current.set(key, { src, group });
  groups.push(group);
};

// prune keys that no longer exist, or the Map grows for the component's lifetime
for (const k of cacheRef.current.keys()) if (!liveKeys.has(k)) cacheRef.current.delete(k);
```

Result: 50 → 0 renders per token.

**Two things this pattern must get right**, both learned the hard way:

- **Prune.** A `Map` keyed by a string is not a `WeakMap`; without pruning it
  leaks for as long as the component stays mounted. `WeakMap` keyed by the source
  object is preferable when a suitable object key exists, precisely because
  entries die with it.
- **Do not over-cache.** The cache must still miss when the block's own content
  changes, or the live view freezes mid-update. Write that test explicitly.

## Defenses that were already present and still insufficient

Worth knowing, because their presence makes it tempting to conclude the render
path is already optimized:

- reducer preserving message identity across dispatches
- `WeakMap` caches for per-message projections and field rewrites
- context split into volatile / stable / rest slices so the hot slice does not
  rebuild the fat value
- stable `useCallback` wrappers reading handlers from refs
- a wrapper component subscribing only to the stable slice so a provider does not
  remount its children per frame

All correct, all necessary, none sufficient — two leaks bypassed the lot. This is
the lesson: **verify with a counter; do not infer memo effectiveness from the
presence of memoization.**

## Harness pattern

```tsx
const counts = { item: 0, thinking: 0 };

vi.mock('@/components/chat', async () => {
  const R = await import('react');
  const MessageItem = R.memo(function ItemSpy(): React.ReactElement {
    counts.item += 1;
    return R.createElement('div');
  });
  const ThinkingBlock = R.memo(function BlockSpy(): React.ReactElement {
    counts.thinking += 1;
    return R.createElement('div');
  });
  const Noop = (): null => null;
  return { MessageItem, ThinkingBlock, /* stub every other export the parent imports */ };
});

// then, per history size:
//   render once -> reset counters (exclude mount) -> drive N events -> read counters
```

Notes that save time:

- Stub **every** export the parent imports from a mocked module, or the render
  throws on an undefined component.
- Mock the context hooks with values that are stable across frames, so the only
  thing changing between renders is the item under test. Otherwise the harness
  measures its own churn.
- Reset counters *after* the initial mount — mount cost is not the bug.
- Annotate spy return types (`: React.ReactElement`, `: null`) if the project
  runs `noImplicitAny`; `tsc` flags bare `memo(function () {...})` factories.
- Vitest may warn about terminating the worker for a heavy render test. Run the
  file standalone to confirm it is a teardown artifact, not a leaked timer.
