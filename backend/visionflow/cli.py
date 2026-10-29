"""Command-line interface — the CLI fallback from the PRD plus a standalone
worker process (for real `kill -9` recovery, not just the in-process demo)."""
from __future__ import annotations

import time
import json
from pathlib import Path

import typer

from . import bootstrap  # noqa: F401
from . import db, store
from .engine import advance, worker
from .engine.replay import derive_state

app = typer.Typer(add_completion=False, help="VisionFlow CLI")


@app.command()
def initdb():
    """Create the schema."""
    db.init_schema()
    typer.echo("schema ready")


@app.command()
def reset():
    """Delete all runs/events (keeps schema)."""
    db.init_schema()
    db.reset_all()
    typer.echo("reset done")


@app.command("run-batch")
def run_batch(count: int = 20, normal_ratio: float = 0.6, seed: int = 0):
    """Submit a batch of inspection runs."""
    import random
    rng = random.Random(seed)
    for i in range(count):
        kind = "normal" if rng.random() < normal_ratio else "defect"
        rid = store.start_workflow("inspection", {"image_id": f"{kind}_{i:04d}"})
    typer.echo(f"submitted {count} runs")


@app.command("make-samples")
def make_samples(train: int = 40, test_good: int = 20, test_defect: int = 20):
    """Generate the real sample image dataset under data/samples/."""
    from .cv import samples
    info = samples.generate(train, test_good, test_defect)
    typer.echo(f"samples ready: {info}")


@app.command()
def fit():
    """(Re)build the anomaly detector memory bank from data/samples/train/good."""
    from .cv import service
    info = service.refit()
    typer.echo(f"detector fitted: {info}")


@app.command()
def evaluate(output: Path | None = None):
    """Evaluate local sample images; optionally save a reproducible JSON report."""
    from .config import settings
    from .cv import service
    from .cv.evaluate import report
    det = service.get_detector()
    try:
        result = report(det, settings.samples_dir, settings.bank_path,
                        settings.t_low, settings.t_high)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)
    metrics = result["metrics"]
    typer.echo(f"image-level AUROC: {metrics['auroc']:.3f}  "
               f"(good mean {metrics['good_mean']:.3f}, defect mean {metrics['defect_mean']:.3f})")
    typer.echo(f"missed defects: {metrics['missed_defect_rate']:.1%}; "
               f"false rejects: {metrics['false_reject_rate']:.1%}; "
               f"human review: {metrics['review_rate']:.1%}")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        typer.echo(f"report saved: {output}")


@app.command()
def run_worker(poll: float = 0.2):
    """Run the worker loop in THIS process (Ctrl-C to stop; safe to restart)."""
    typer.echo("worker started; Ctrl-C to simulate a crash")
    try:
        while True:
            ids = store.runnable_run_ids()
            if not ids:
                time.sleep(poll)
                continue
            for rid in ids:
                advance(rid)
    except KeyboardInterrupt:
        typer.echo("\nworker stopped")


@app.command("list-paused")
def list_paused():
    """List runs awaiting human review."""
    q = store.review_queue()
    if not q:
        typer.echo("(no runs awaiting review)")
    for r in q:
        typer.echo(f"{r['run_id']}  score={r['score']:.3f}  image={r['image_id']}")


@app.command()
def show(run_id: str):
    """Show a run's score, heatmap path, and event log."""
    events = store.load_events(run_id)
    if not events:
        typer.echo("not found"); raise typer.Exit(1)
    st = derive_state(events)
    typer.echo(f"status={st['status']} stage={st['stage']} score={st['score']} "
               f"verdict={st['verdict']} heatmap={st['heatmap']}")
    for e in events:
        typer.echo(f"  #{e.seq:<3} {e.event_type} {e.payload}")


@app.command()
def verdict(run_id: str, verdict: str):
    """Submit a human verdict (pass|reject) to a paused run."""
    if verdict not in ("pass", "reject"):
        typer.echo("verdict must be pass|reject"); raise typer.Exit(1)
    store.append_simple(run_id, "SIGNAL_RECEIVED",
                        {"name": "human_verdict", "data": {"verdict": verdict}})
    worker.refresh_cache(run_id)
    typer.echo(f"verdict '{verdict}' delivered; run will resume")


def main() -> None:
    try:
        app()
    except db.DatabaseUnavailable as e:
        typer.secho(f"\nDatabase unavailable:\n{e}", fg=typer.colors.RED, err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
