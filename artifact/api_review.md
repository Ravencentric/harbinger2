# Harbinger Pre-1.0 Review

> **Verdict**: This is a well-scoped, well-written project. The code is clean, the module boundaries are correct, and the public API is almost exactly the right size. Most of the issues below are fit-and-finish problems — things that are 80% right but would calcify in the wrong shape if shipped as-is. Nothing needs a rewrite. Several things need a reshape.

---

## 1. Public API

### 1.1 The API surface is nearly perfect

`from harbinger import task` — one symbol, one concept. This is correct. Ship it.

### 1.2 `TaskSpec` is an internal concept leaking through the decorator

[TaskSpec](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/model.py#L26-L30) exists solely as a struct to shuttle `name`/`description`/`default` from `@task(...)` to `Task.from_func()`. It's created in one place ([registry.py:46](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/registry.py#L46)) and consumed in one place ([model.py:42](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/model.py#L42)). This is a named type for what is essentially three keyword arguments being passed one call down.

**Problem**: It adds a concept users never see but contributors must understand. It also splits the construction logic: `task()` builds a `TaskSpec`, then `Task.from_func()` unpacks it. The intermediate object buys nothing.

**Proposal**: Delete `TaskSpec`. Have `Task.from_func()` take `name`, `description`, and `default` directly. Or, since the marker on the function already carries these values, store them as a plain dict/tuple on the marker attribute. The dataclass adds type safety for something that crosses exactly one function boundary inside a single module.

**Tradeoff**: Marginally less self-documenting at the marker site. Saved: one class, one import, one concept.

**Worth it?** Yes. It's a private intermediate — kill it.

---

### 1.3 `MARKER` as a string attribute is fine, but the stamping pattern has a subtle bug

```python
setattr(fn, MARKER, spec)
```

[registry.py:51](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/registry.py#L51)

This stamps the *function object*. If the user wraps a task with `functools.wraps` or another decorator that copies attributes, `MARKER` will be copied to the wrapper, and the same function could end up registered twice — once as the inner, once as the outer. `AlreadyTaskError` catches double-`@task`, but it won't catch a subsequent decorator that `@wraps` the already-marked function.

**Problem**: A user stacking `@task` with any `@wraps`-based decorator (logging, retry, timing — extremely common) will silently register the wrapper. The wrapper's `__name__` will differ from the inner's, so `AlreadyTaskError` won't fire, and `DuplicateTaskNameError` might or might not fire depending on whether the wrapper preserves `__name__`.

**Proposal**: No code change strictly needed — but the README should explicitly document decorator ordering (`@task` must be outermost) or the marker should be checked on the unwrapped function via `inspect.unwrap()`.

**Worth it?** Yes, at least as documentation. A one-line `inspect.unwrap()` check in the decorator would be better.

---

### 1.4 `default=True` is backwards

Every task is `default=True` unless you opt out. The README says:

> Tasks are included in `--default` by default. Mark composite/aggregator tasks with `default=False`.

This means `harbinger --default` runs everything except the tasks the user explicitly excluded. That's just `--all` with a deny list. In every real project I've seen, the *minority* of tasks are "default" (build, test, lint) and the majority are utility tasks (deploy, clean, docs, release, greet, echo).

**Problem**: The default (pun intended) is wrong. Most users will end up annotating most tasks with `default=False`, which is noisy. The semantics of `--default` become "run everything except what I remembered to exclude," which is fragile.

**Proposal**: Flip it. `default=False` by default. Users opt *in* to the default set with `@task(default=True)` or a shorter alias like `@task(default=True)`. The `--default` flag then means "run the curated set."

Alternatively — and I lean toward this — delete the `default` concept entirely and let users compose tasks by calling them directly (which is already shown in the README's `ci()` example). The `--default` flag adds a concept that creates more confusion than it saves keystrokes. `harbinger --all` and `harbinger lint test` cover the use cases.

**Tradeoff**: If you keep `default`, flipping the polarity is a one-line change. If you delete it, you lose `harbinger -d` as a shorthand. But `harbinger -d` only works if you've carefully annotated all tasks, and users won't.

**Worth it?** Strongly yes, either flip or delete. The current default is the wrong default.

---

### 1.5 `LiteralType` is a good idea but the restriction to `str`-only Literals is surprising

[annotation.py:41-44](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/annotation.py#L41-L44) accepts `Literal["foo", "bar"]` but rejects `Literal[1, 2]`.

**Problem**: This is a paper cut. `Literal[1, 2, 3]` is a perfectly reasonable type for a task parameter (e.g., `verbosity: Literal[0, 1, 2] = 1`). The restriction exists because `argparse.choices` works on strings and the current code doesn't coerce. But the user doesn't know that — they'll try `Literal[1, 2]`, get an opaque `unsupported annotation` error, and be confused.

**Proposal**: Either support `Literal` with homogeneous int/str values (coercion is trivial: set `type=int` on the argparse argument and `choices=(1, 2)`), or document the restriction clearly in the README's type table. The current silent rejection is the worst outcome.

**Worth it?** Yes. Supporting int literals is ~5 lines. Not supporting them should be documented.

---

### 1.6 `EmptyType` is a misleading name

`EmptyType` represents "no annotation / `object` / `Any`" — i.e., the parameter is untyped and will be treated as a raw string. The name `EmptyType` suggests *absence of a parameter* or *a type with no inhabitants* (like `Never`), not "we'll pass it through as a string."

**Proposal**: Rename to `Untyped` or `RawString`. It's one of three variants in a discriminated union — clarity matters.

**Worth it?** Yes. Naming is the API.

---

## 2. Architecture

### 2.1 Module boundaries are correct

The layering is: `annotation` → `signature` → `model` → `registry` → `cli`. No circular imports. Data flows downward. This is good.

### 2.2 `Signature` is a pointless wrapper

[Signature](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/signature.py#L55-L58) is:

```python
@dataclass(frozen=True, slots=True)
class Signature:
    kind: FixedSignature | VariadicSignature
```

A frozen dataclass with a single field named `kind`. Every consumer immediately destructures it: `match self.task.signature.kind`. The `Signature` wrapper adds one level of indirection and zero information.

**Problem**: It's a box around a union. Every access site pays `sig.kind` for nothing. The `parse()` classmethod is the only reason this class exists, and classmethods can live on a module-level function.

**Proposal**: Delete `Signature`. Make `Task.signature` typed as `FixedSignature | VariadicSignature` directly. Move `Signature.parse()` to a module-level `parse_signature(func) -> FixedSignature | VariadicSignature`.

**Tradeoff**: Slightly less "OOP." Fewer indirections, fewer concepts.

**Worth it?** Yes. The wrapper is pure ceremony.

---

### 2.3 `Subparser` mutates `self.parser` during `parse()`

[parser.py:42-80](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/cli/parser.py#L42-L80)

`Subparser.__init__` creates an empty `ArgumentParser`. `Subparser.parse()` then calls `add_kwarg`/`add_arg` to populate it, then calls `parse_args`. This means `parse()` can only be called once — the second call would double-add arguments. But nothing enforces this. The `parser` field is public and mutable.

**Problem**: Hidden single-use invariant. The class looks reusable but isn't.

**Proposal**: Make `Subparser` a function, not a class. It's called in exactly one place. The whole thing is `def parse_task_args(task: Task, argv: Sequence[str]) -> ArgsKwargs`. Build the `ArgumentParser` inside, add arguments, parse, return. No class, no mutable state, no hidden invariant.

**Tradeoff**: None. It's a pure function pretending to be a class.

**Worth it?** Yes.

---

### 2.4 `cli/__init__.py` does too much

[cli/__init__.py](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/cli/__init__.py) is 107 lines of orchestration logic. It has two separate `try/except` blocks catching overlapping exception types (`HarbingerError` appears in both), which is confusing. The first block handles load-time errors, the second handles run-time errors. This makes sense conceptually but the code doesn't make the boundary visible.

**Problem**: The load-time and run-time error handling are interleaved in a single function with two catch-all `HarbingerError` handlers. If a new `HarbingerError` subclass is added, it's unclear which handler will catch it first. The first handler *re-raises* `HarbingerError` from `TaskDefinitionError` upward, which masks the intent.

Wait — re-reading: the first block is `except TaskFileNotFoundError` / `except TaskDefinitionError` / `except HarbingerError`. `TaskDefinitionError` is a subclass of `HarbingerError`, so ordering matters. This is correct but fragile.

**Proposal**: Split into `load() -> TaskRegistry | int` (returns error code on failure) and `execute(registry, cmd) -> int`. Separate the phases explicitly. This also enables testability: you can test command dispatch without loading a file.

**Tradeoff**: One more function. More testable, more readable.

**Worth it?** Mild yes.

---

### 2.5 `command()` eagerly parses before the registry exists

[parser.py:146](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/cli/parser.py#L146) parses `sys.argv` into a `Command` *before* the task file is loaded. This means:

1. `harbinger nonexistent-task` parses successfully as `RunSelected(names=("nonexistent-task",))`.
2. The registry is loaded.
3. The name is validated.

This ordering is fine *today*, but it means `command()` can't validate task names against the registry. It also means `--version` still triggers a task-file load (since `command()` handles `--version` via argparse's `action="version"` which calls `sys.exit` before returning, so the load never happens — but only by accident, not by design).

**Problem**: `--version` working without a task file is accidental, not intentional. If argparse's `action="version"` ever changes behavior, `harbinger --version` breaks when run outside a project.

**Proposal**: Handle `--version` (and maybe `--help`) explicitly before loading the task file. This makes the contract visible.

**Worth it?** Mild yes. Defensive against a real user scenario (running `harbinger --version` outside a project root).

---

## 3. Domain Modeling

### 3.1 `Parameter.default` is `object` — allows invalid states

[signature.py:38](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/signature.py#L38)

```python
default: object
```

This field can hold literally anything. The parse logic already validates that a default exists (it raises `MissingDefaultError`), but then stores the value as `object`. Worse, line 112-116 has:

```python
default=(
    None
    if param.default is inspect.Parameter.empty
    else param.default
),
```

This branch is *dead code* — `MissingDefaultError` was already raised on line 92 if the default is `empty`. The `None` fallback can never execute.

**Problem**: Dead code and an overly loose type. `Parameter.default` should be typed as `Scalar` (i.e., `int | float | str | bool | Path`) since those are the only types the system supports. This would catch bugs at construction time.

**Proposal**: Type `default` as `Scalar | None`, remove the dead `None` branch, and assert at parse time that the default matches the annotation's type.

**Tradeoff**: Slightly stricter — a user who sets `default=some_exotic_object` gets a clear error instead of silent pass-through. This is good.

**Worth it?** Yes. Dead code in a pre-1.0 is a red flag. Fix it now.

---

### 3.2 `ParameterKind` should not exist as a separate enum

[signature.py:22-30](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/signature.py#L22-L30)

`ParameterKind` has two values: `POSITIONAL` and `KEYWORD`. It's used in exactly two places: when constructing a `Parameter`, and in `Subparser.parse()` to dispatch between `add_arg` and `add_kwarg`. The enum has helper methods `is_positional()` and `is_keyword()` that are just identity comparisons.

**Problem**: This is `inspect.Parameter.kind` with fewer values and no additional semantics. The helpers `is_positional()` / `is_keyword()` are trivial one-liners that repeat what `is` comparison already does. The enum doesn't justify its existence.

**Proposal**: Either inline the boolean (`is_keyword: bool` on `Parameter`), or — better — make the distinction structural: have `PositionalParam` and `KeywordParam` as separate dataclasses. This would let the parser dispatch by type (which it already does by kind value), and the keyword-only-bool invariant would be enforced at the type level rather than at parse time.

**Tradeoff**: More types but each type is more constrained. Alternatively, `is_keyword: bool` is simpler and loses nothing.

**Worth it?** Mild yes. The enum is one of those "looks like it buys something but doesn't" abstractions.

---

### 3.3 `Task.call()` swallows the return value

[model.py:56-60](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/model.py#L56-L60)

```python
def call(self, *args: object, **kwargs: object) -> None:
    try:
        self.func(*args, **kwargs)
    except Exception as source:
        raise TaskError(self.name) from source
```

This silently discards whatever the task function returns. The `-> None` signature is a lie — the user's function could return anything. This is fine *today* but precludes ever doing anything with return values (e.g., task composition, piping, dry-run introspection).

**Problem**: Not a bug today, but a design constraint that should be intentional. If you never want return values, the decorator should enforce `-> None` at registration time.

**Proposal**: Either validate at registration that the return annotation is `None`, or don't discard the return value. Pick a lane.

**Worth it?** Mild yes. Validates a contract you're already implicitly assuming.

---

### 3.4 `VariadicSignature` can't have keyword-only args

The README says:

> The keyword-only case (`*args` plus `--flag` options) is unambiguous and may be lifted if the need arises.

This is noted as a future relaxation. The domain model reflects the current restriction: `VariadicSignature` has no `parameters` field. This is honest modeling — the type system prevents constructing a state the code doesn't support. Good.

But the restriction itself is questionable for a 1.0. `*args` plus keyword flags is the most natural CLI pattern (`cp -r src dst1 dst2`). Shipping without it means users can't express common task signatures.

**Proposal**: Support it before 1.0. The model change is adding `keywords: Sequence[Parameter]` to `VariadicSignature`. The parser change is adding keyword args before `parse_args`. It's not hard.

**Worth it?** Yes, if you want the tool to be useful beyond trivial tasks.

---

## 4. Ergonomics

### 4.1 `harbinger greet -- Alice` is awkward

The `--` separator is a unix convention for "end of options," not for "start of task arguments." Users will try `harbinger greet Alice` and be confused when it tries to run both `greet` and `Alice` as tasks (or fails with "unknown task 'Alice'").

**Problem**: The most natural way to pass arguments to a task doesn't work. The `--` is required because the parser can't distinguish between task names and task arguments without it. This is a fundamental UX tradeoff.

**Proposal**: This is honestly fine as long as it's well-documented. The alternative (per-task subcommands like `invoke`) requires knowing task names at parse time, which requires loading the task file before parsing, which creates a chicken-and-egg problem. The `--` design is a reasonable compromise. Just make sure the error message when someone writes `harbinger greet Alice` suggests using `--`.

**Worth it?** Not a code change — an error-message improvement.

---

### 4.2 `console.render()` uses string replacement, which is fragile

[console.py:59-68](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/cli/console.py#L59-L68)

```python
for style in Style:
    if color:
        s = s.replace(style.marker, style.to_ansi())
    else:
        s = s.replace(style.marker, "")
```

If someone's task output contains the literal text `[cyan]`, it'll be replaced with ANSI codes. This is an injection vulnerability for user-controlled strings. The error formatting in `fmt.py` interpolates exception messages (which come from user code) into styled strings.

**Problem**: Task exception messages can accidentally (or intentionally) inject color codes into harbinger's output.

**Proposal**: Escape `[` in user-controlled strings before interpolation, or switch to a structured approach where styled segments are objects, not embedded markers. Given the project's size, escaping is sufficient.

**Worth it?** Yes. This is a correctness bug. Exception messages like `"expected [red] channel"` will produce garbled output.

---

### 4.3 `can_colorize()` checks `sys.stdout` but errors go to `sys.stderr`

[console.py:50-56](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/cli/console.py#L50-L56) checks if stdout is a TTY. But `console.error()` and `console.hint()` write to stderr. If stdout is redirected but stderr is a TTY (common: `harbinger greet > out.txt`), the error messages will lose their color even though they're going to a terminal.

**Problem**: Colors in error output are gated on the wrong file descriptor.

**Proposal**: Either check both stdout and stderr independently (render differently per stream), or check stderr for stderr output. The simplest fix: `render()` takes a `stream` parameter and checks that stream's TTY-ness.

**Worth it?** Yes. This is a real bug users will hit.

---

## 5. Simplicity

### 5.1 `errors.py` has too many exception classes

Seven `TaskDefinitionError` subclasses, each carrying slightly different combinations of `task` and `param` strings. All of them are caught in exactly one place (`fmt.py:diagnostic_for`) and converted to a `(error, hint)` tuple.

**Problem**: The exception hierarchy is doing the job of a discriminated union. Each class exists solely to carry data to `diagnostic_for`. The `match` statement in `diagnostic_for` is the *real* logic; the exceptions are just transport.

**Proposal**: Collapse into a single `TaskDefinitionError` with an enum `kind` field (or a `Literal` type) and the relevant fields. The `match` in `diagnostic_for` switches on `kind` instead of exception type. This cuts 7 classes to 1 class + 1 enum.

Alternatively, keep the classes — they *are* the enum, structurally. The current design is honest; it's just verbose. This is a taste call.

**Tradeoff**: Fewer types vs. structural exhaustiveness in `match`. Python's `match` on exception types is already a bit unusual; switching to an enum `kind` is more conventional.

**Worth it?** Soft yes. The verbosity is tolerable but the pattern is fighting the language.

---

### 5.2 `HarbingerError.causes()` duplicates stdlib

[errors.py:11-17](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/errors.py#L11-L17)

Python 3.11+ has `BaseException.__notes__` and the cause chain is already accessible via `__cause__`. The `causes()` method is a simple linked-list walk that could be a standalone function (or even a generator). Having it as a method on the base error class means every error subclass carries it, but only `fmt.py` calls it.

**Problem**: It's not *wrong*, but it's a method on a class that doesn't need it. It's presentation logic living on a domain type.

**Proposal**: Move to `fmt.py` as a free function `def causes(e: HarbingerError) -> list[BaseException]`. It's only used there.

**Worth it?** Yes, but low priority.

---

### 5.3 The `cli` subpackage could be a single module

`cli/__init__.py` (107 lines), `console.py` (89 lines), `fmt.py` (140 lines), `parser.py` (215 lines). That's ~550 lines across four files. The inter-file dependencies are tight (`fmt` imports `console`, `__init__` imports everything). There's no reuse of `console` or `fmt` outside `cli`.

**Problem**: Four files where one or two would do. The module boundaries don't represent meaningful reuse boundaries — they represent "this felt like a different concern." But the concerns are tightly coupled and small.

**Proposal**: Merge `console.py` and `fmt.py` into a single `output.py` or even inline into `cli/__init__.py`. Alternatively, keep `parser.py` separate (it's the most independent) and merge the rest. The subpackage promotes to a module if you merge enough.

**Tradeoff**: Fewer files to navigate vs. longer files. At 550 total lines, this is taste. But having a `cli` *package* with an `__init__.py` that does heavy lifting is an anti-pattern — packages should be organizers, not workers.

**Worth it?** Soft yes. Taste call.

---

### 5.4 `TaskFn` Protocol is over-engineered for its use

[model.py:14-18](file:///C:/Users/raven/dev/github/harbinger2/src/harbinger/model.py#L14-L18)

```python
class TaskFn(Protocol, Generic[P, R]):
    @property
    def __name__(self) -> str: ...
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...
```

Used with `ParamSpec` and a covariant `TypeVar`. The `TaskDecorator` alias uses both. But in practice, every `TaskFn` in the codebase is typed as `TaskFn[..., object]` — the generic parameters are never meaningfully instantiated. The `P` and `R` only exist to make the decorator overloads look correct to type checkers.

**Problem**: The generics serve the type checker, not the code. This is fine in principle, but the Protocol + ParamSpec + covariant TypeVar combination is the most complex type machinery in the project, deployed in service of a decorator that stamps an attribute. If a type checker can't handle `Callable` with `__name__`, the Protocol is justified. If it can, it isn't.

**Proposal**: Check if `Callable[P, R]` with a `typing.Protocol` is actually needed for type-checker compatibility, or if `Callable[..., Any]` plus a `cast` in the decorator is sufficient. If the Protocol is genuinely needed for correctness, keep it. If it's aspirational, delete it.

**Tradeoff**: Type-checker correctness vs. complexity. In a library this size, the Protocol is a large share of the type complexity.

**Worth it?** Investigate, then decide. Don't ship complex types that aren't tested against the type checker.

---

## 6. Excellent Decisions

A few things that are unambiguously good:

- **Zero dependencies.** The project uses only stdlib. This is the right call for a task runner.
- **`snake_case` → `kebab-case` normalization.** Convention-based, unsurprising, correct.
- **`parse, don't validate` in `annotation.py`.** The `parse()` function returns a union type or `None`. The caller handles the `None`. No exceptions for expected cases. This is textbook.
- **`from harbinger import task`** — single-symbol API. Best possible surface.
- **Error cause chains.** The `TaskError` wrapping with `from source` preserves the original traceback. The formatted output with `location_of()` showing file:line:col is genuinely useful and better than most task runners.
- **Frozen dataclasses everywhere.** Immutability by default is correct.
- **The `--` design for argument passing.** It's unusual but it's *right* — it avoids the subcommand bootstrapping problem without requiring task-file loading before arg parsing.

---

## 7. Summary Table

| Issue | Severity | Effort | Recommendation |
|---|---|---|---|
| Delete `TaskSpec` | Low | Trivial | Do it |
| `default=True` polarity (or delete `default`) | High | Trivial | Flip or delete |
| `Signature` wrapper is pointless | Medium | Trivial | Delete |
| `Subparser` should be a function | Medium | Trivial | Refactor |
| Dead code in `Parameter.default` construction | Medium | Trivial | Remove |
| `EmptyType` name is misleading | Low | Trivial | Rename |
| Color injection from user strings | High | Low | Escape user text |
| `can_colorize` checks wrong stream | Medium | Low | Fix |
| Support `*args` + keyword params | Medium | Medium | Implement |
| Support `Literal[int]` | Low | Low | Implement or document |
| `--version` without task file is accidental | Low | Low | Make explicit |
| `ParameterKind` enum overhead | Low | Low | Simplify |
| Exception class proliferation | Low | Medium | Taste call |
| Decorator stacking / `@wraps` hazard | Medium | Low | Document or detect |
| `TaskFn` Protocol complexity | Low | Low | Audit necessity |

---

## 8. Final Assessment

This project is close to 1.0-ready. The design instincts are sound: small API, zero deps, parse-don't-validate, immutable data. The issues are:

1. **Two genuine bugs** (color injection, wrong TTY check) that need fixing.
2. **One wrong default** (`default=True`) that will cause user friction if shipped.
3. **Several unnecessary abstractions** (`Signature`, `TaskSpec`, `Subparser` class, `ParameterKind` enum) that should be simplified before the API surface calcifies.
4. **One missing feature** (`*args` + keywords) that limits the tool's usefulness.

Fix those and it's a solid 1.0.
