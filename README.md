# VisionFlow

**A durable execution engine for a computer-vision defect-inspection pipeline.**

VisionFlow runs each inspected image as an *event-sourced workflow* —
`load image → AI check → decision → (optional) human review → finalize`.
A worker crash at any point loses no work, never recomputes a finished AI check,
and never fires a side effect (verdict, alert) twice. Ambiguous cases park
durably for a human and resume on a signal — without holding a process open.

**The computer vision is real and runs on any CPU.** The default `local` backend
is a classical patch-based anomaly detector (feature memory bank + nearest-
neighbour distance, in the spirit of PatchCore) that learns "normal" from
defect-free images and flags anything unlike them, with a heatmap of *where*. It
needs no GPU and no dataset download, and it scores **AUROC 1.000** separating the
included good vs. defective sample images. A deep PatchCore backend (torch +
MVTec AD) is available behind one env var; a pure simulator exists for ultra-light
demos.

You can **drag any image onto the "Check Image" page** and get a saved inspection with a verdict
(looks fine / defect found / needs a person) with the heatmap — so a non-technical
person can actually use it, not just read about it.

> Built from the VisionFlow Lite PRD. The frontend adopts the dark-glass "Pravah"
> design language supplied as the UI reference.

---

## Why this is interesting

A model that outputs an anomaly score is not an inspection *system*. A real line
needs three outcomes — auto-pass, auto-reject, or route-to-human — and must
survive crashes and multi-day review pauses mid-pipeline without losing or
duplicating work. That orchestration problem is what VisionFlow solves, and it is
genuine distributed-systems engineering rather than another model wrapper.

---

## Architecture

```
                         ┌─────────────────────────────────────────────┐
  React + Vite UI  ◀────▶│  FastAPI  (/api/*, /data/*, SSE-ish polling) │
  (dark-glass theme)     └───────────────┬─────────────────────────────┘
   • Pipeline (live flow + crash demo)   │
   • Review queue (heatmap + verdict)    │        ┌──────────────────────┐
   • How It Works (explainability)       ├───────▶│  Controllable Worker  │
   • Run drawer (event-log timeline)     │        │  advance(run): replay │
                                         │        │  history, run the     │
                                         │        │  frontier activity    │
                                         ▼        └───────────┬───────────┘
                             ┌───────────────────────┐        │
                             │  Postgres              │        ▼
                             │  • events (append-only │   ┌─────────────────┐
                             │    = source of truth)  │   │ Activities       │
                             │  • run_status (cache)  │   │  ingest          │
                             │  • verdicts / alerts   │◀──│  run_inference ──┼─▶ CV backend
                             │    (idempotent sinks)  │   │  write_verdict   │   • simulate (default)
                             │  • effect_log (cache)  │   │  send_alert      │   • patchcore (opt-in)
                             └───────────────────────┘   └─────────────────┘
```

Core modules (`backend/visionflow/`):

| Module | Responsibility |
|---|---|
| `events.py` | Event vocabulary; the log is the only source of truth. |
| `store.py` | The only writer of the log; atomic `seq` allocation; idempotent sinks. |
| `engine/replay.py` | Pure fold `events → state` (the read model; FR6). |
| `engine/context.py` | `call_activity` (replay vs. execute-once) and `wait_for_signal` (suspend). |
| `engine/worker.py` | `advance(run)` + the controllable worker thread. |
| `engine/crash.py` | Deterministic crash injection for tests and the demo button. |
| `activities/` | ingest, inference, write_verdict, send_alert (+ a toy_add for tests). |
| `workflows/` | the `inspection` workflow and a `toy_adder` for crash tests. |
| `cv/simulate.py` | deterministic scorer + heatmap PNGs (no torch). |
| `cv/patchcore.py` | real PatchCore (frozen WideResNet-50, coreset memory bank). |
| `api/app.py` | HTTP surface + worker controls. |
| `cli.py` | standalone worker + review commands. |

---

## Run it with one command (Docker)

The easiest way — starts the database, backend, worker, and website together:

```bash
docker compose up --build
# then open  http://localhost:5173
```

Nothing else to install, no accounts, no API keys. The first start builds the
sample images and the detector automatically.

---

## Quick start (manual, for development)

Prereqs: **Python 3.11+**, **Node 18+**, and **Postgres 16** reachable. No cloud
accounts, no API keys — the CV runs locally on your CPU.

```bash
# 0. (option A) use your local Postgres, or (option B) docker compose up -d
#    Default URL expected:
#    postgresql://visionflow:visionflow@127.0.0.1:5432/visionflow
#    Create it once:
#      createuser visionflow --login --pwprompt   # password: visionflow
#      createdb  -O visionflow visionflow

# 1. Backend
cd backend
pip install -r requirements.txt
python -m visionflow.cli initdb
python -m visionflow.cli make-samples   # write the real sample images
python -m visionflow.cli fit            # build the detector memory bank
python -m visionflow.cli evaluate       # prints image-level AUROC

# 2. API + in-process worker (terminal 1)
python -m uvicorn visionflow.api.app:app --reload --port 8000

# 3. Frontend (terminal 2)
cd ../frontend
npm install
npm run dev            # http://localhost:5173  (proxies /api and /data to :8000)
```

Then open http://localhost:5173, click **Submit batch**, watch runs flow through
the pipeline, hit **Simulate crash**, then **Restart worker** and watch in-flight
runs resume. Ambiguous runs appear under **Review**.

A `Makefile` wraps all of this: `make help`.

---

## Deploying (Vercel + Render)

Vercel can host the **frontend** but not the backend: the durable worker is an
always-running process and needs a real database and filesystem, which serverless
doesn't provide. So split it: frontend on Vercel, backend + Postgres on a process
host (Render shown here; Railway/Fly work the same way).

**1. Backend + database on Render**
- New → **Blueprint** → pick this repo. `render.yaml` provisions the Docker web
  service **and** a free Postgres, wired together.
- When it's live, open `https://<your-api>.onrender.com/api/health` — it should
  return `{"ok": true, ...}`.

**2. Frontend on Vercel**
- New Project → this repo → set **Root Directory = `frontend`** (Vite is
  auto-detected; `frontend/vercel.json` handles SPA routing).
- Add an env var **`VITE_API_URL`** = your Render API URL
  (e.g. `https://visionflow-api.onrender.com`). Deploy.

**3. Lock CORS**
- Back in Render, set **`VF_CORS_ORIGINS`** to your Vercel URL
  (e.g. `https://visionflow.vercel.app`) and redeploy.

**Notes for the free tier**
- Render free instances sleep after inactivity; the first request wakes them in
  ~30–60s, and the worker resumes from the event log (nothing is lost).
- Uploaded images and heatmaps live on the instance's disk, so they reset on
  redeploy. Samples and the detector rebuild automatically on startup.
- Keep it to **one instance** — multiple instances would each run a worker.

## The money demo (crash recovery)

1. On **Pipeline**, submit a batch of ~60 (set a visible `VF_SIM_DELAY_MS`, e.g. 300).
2. Hit **Simulate crash** — the worker is armed to die right after an `ingest`
   boundary, mimicking `kill -9`. The nav worker pill turns red.
3. Open the **run drawer** on a half-finished run: its event log stops partway;
   the derived state is rebuilt purely from those events.
4. Hit **Restart worker**. A fresh worker replays each run's log, skips everything
   already recorded (no re-inference), and continues. No verdict or alert is
   duplicated.

For a *real* process kill (not the in-process button), run the standalone worker
(`python -m visionflow.cli run-worker`), `Ctrl-C` it mid-batch, and start it again.

---

## Tests (map to the PRD functional requirements)

```bash
cd backend && VF_SIM_DELAY_MS=0 python -m pytest
```

| Test | Proves |
|---|---|
| `test_replay.py::test_fold_is_deterministic` | FR6 — folding the log twice is identical. |
| `test_replay.py::test_state_reconstructs_from_events_only` | FR5 — state derives only from events. |
| `test_idempotency.py` | FR9 — verdict/alert written exactly once. |
| `test_crash_recovery.py` (parametrized over every boundary) | FR8/FR10 — crash at any point → correct resume, exactly-once side effects. |
| `test_crash_recovery.py::test_side_effect_body_ran_twice_but_effect_once` | The crisp exactly-once proof: body executes twice, sink row appears once. |
| `test_crash_recovery.py::test_pause_and_resume_on_signal` | FR8/FR11 — durable pause + resume on human verdict. |

All 11 pass against a live Postgres.

---

## Is the computer vision real?

Yes. There are three interchangeable backends (set `VF_CV_BACKEND`):

| Backend | What it is | Needs |
|---|---|---|
| `local` (default) | Classical patch-based anomaly detector on real pixels: patch features → normal-patch memory bank → nearest-neighbour distance → score + heatmap. | numpy only (any CPU) |
| `patchcore` | Deep PatchCore: frozen WideResNet-50 features, coreset memory bank. | torch + MVTec AD |
| `simulate` | Deterministic fake score from the filename (fast demos only). | nothing |

The `local` detector genuinely reads pixels and learns "normal" from defect-free
images. On the bundled samples it reports:

```
image-level AUROC: 1.000  (good mean 0.17, defect mean 1.00)
```

Rebuild/evaluate any time:

```bash
python -m visionflow.cli make-samples     # (re)write data/samples
python -m visionflow.cli fit              # rebuild the memory bank
python -m visionflow.cli evaluate         # AUROC on the test split
```

### Using the real MVTec dataset (optional, for a deep-model CV story)

```bash
pip install torch torchvision
export VF_CV_BACKEND=patchcore
export VF_MVTEC_ROOT=/path/to/mvtec/bottle   # free registration at mvtec.com
```

MVTec AD is the standard industrial anomaly-detection benchmark; the `bottle`
category is a good first choice (~200 MB). `cv/patchcore.py` builds a memory
bank from `train/good` and scores test patches by nearest-neighbour distance —
the durable engine is identical for all three backends.

---

## Design notes / hardest parts (the interesting bugs)

These are the subtleties that make this more than a CRUD app — and the best
interview fodder.

1. **The exactly-once window is at the *sink*, not the event log.**
   The naive idea ("cache the result, then append the event") still double-fires
   if the worker dies *after* the side effect but *before* the cache/event commit.
   The fix: every side effect writes to a table whose PRIMARY KEY is the
   deterministic idempotency key (`run:callindex:activity`) with
   `ON CONFLICT DO NOTHING`. On replay the activity re-runs, but the insert is a
   no-op. `test_side_effect_body_ran_twice_but_effect_once` pins this down: the
   activity body runs **twice**, the sink row exists **once**.

2. **Determinism is a boundary, not a hope.**
   Progress is made by re-running the workflow function from the top against
   history. That only works if workflow code is pure — so all non-determinism
   (the model, clocks, randomness, I/O) is forced into *activities*, whose results
   are recorded and replayed. Branch decisions (pass/reject/review) read the
   recorded score, so the same branch is taken on every replay and activity call
   indices never shift.

3. **`seq` allocation under concurrency.**
   The API thread (appending signals) and the worker thread (appending activity
   events) both write to the same run. `seq` is allocated as
   `MAX(seq)+1` *inside the insert*, and `UNIQUE(run_id, seq)` turns any race into
   a retryable conflict rather than a silently corrupted log.

4. **Suspend is an event, so PAUSED is derivable.**
   Rather than track "waiting" in a side table, suspension appends a
   `WORKFLOW_SUSPENDED` event and a verdict appends `SIGNAL_RECEIVED`. The fold
   decides PAUSED vs. RUNNING purely from which came last — keeping the "state is
   only ever derived from the log" invariant intact.

5. **`CREATE TABLE IF NOT EXISTS` does not migrate.**
   Adding `stage`/`n_events` columns to an already-created `run_status` silently
   did nothing until the table was dropped — a reminder that schema evolution
   needs real migrations, not idempotent creates. (Documented here so the next
   person drops the table or adds an `ALTER`.)

---

## Deliberate deviations from the PRD

- **A web frontend was added** (the PRD scoped review to a CLI). The CLI still
  exists (`visionflow.cli`), but the UI makes the flow and the event-sourcing
  story far easier to explain and demo. The crash button, the run-drawer timeline,
  and the drag-and-drop "Check Image" page are things a CLI can't match.
- **The CV runs on CPU by default** via a real classical anomaly detector, so the
  system does genuine computer vision with no GPU/dataset. Deep PatchCore (MVTec)
  and a pure simulator are both one env var away; the engine is identical for all.

---

## Repository layout

```
visionflow/
  backend/
    visionflow/{config,events,db,store}.py
    visionflow/engine/{sdk,context,replay,worker,crash,errors}.py
    visionflow/activities/__init__.py
    visionflow/workflows/__init__.py
    visionflow/cv/{simulate,patchcore}.py
    visionflow/api/app.py
    visionflow/cli.py
    tests/{test_replay,test_idempotency,test_crash_recovery}.py
  frontend/            # Vite + React + TS, dark-glass theme
    src/{pages,components,hooks,api,lib}/...
  data/{images,heatmaps}/      # generated on demand
  docker-compose.yml  Makefile  .env.example
```

## Durable uploads and evaluation reports

`POST /api/inspect` validates an image (maximum 10 MB and 20 megapixels), stores
it as PNG, and returns HTTP 202 with `{"run_id": "..."}`. Poll
`GET /api/runs/{run_id}` for progress. The Check Image page does this automatically.
Uploads use the worker, appear in Pipeline history, and enter Review when ambiguous.
If the worker is stopped, uploads stay queued until it restarts.

New inspection runs record their decision thresholds and selected backend in the
start event. Changing those settings does not alter new runs already in progress.
Existing histories without a saved policy retain legacy behavior. Model artifacts
are not yet pinned per run; avoid replacing a detector while inspections are pending.

Generate a machine-readable evaluation report with:

```bash
cd backend
python -m visionflow.cli evaluate --output ../data/evaluation.json
```

The report records model and test-image SHA-256 hashes, individual scores,
thresholds, tie-correct AUROC, missed-defect rate (defects auto-passed), false-reject
rate (good images auto-rejected), and review rate across all test images. Threshold
boundary scores enter review. Results describe the bundled synthetic dataset,
not general performance on arbitrary product photos.
