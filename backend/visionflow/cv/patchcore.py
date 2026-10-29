"""Real PatchCore backend (opt-in via VF_CV_BACKEND=patchcore).

This is the Week-1 CV deliverable from the PRD: an unsupervised anomaly
detector that learns "normal" from defect-free MVTec AD images only, then scores
new images by how far their patch embeddings sit from the bank of normal
embeddings. It requires torch + torchvision + an MVTec category on disk, so it
is intentionally lazy-imported and never touched when running in simulate mode.

Pipeline:
  1. Frozen pretrained WideResNet-50 backbone; take layer2 + layer3 feature maps.
  2. Build a memory bank of patch embeddings from all train/good images.
  3. Coreset-subsample the bank (greedy) to keep nearest-neighbour search fast.
  4. Score a test image per patch by distance to its nearest bank neighbour;
     the image score is the max patch distance; the heatmap is the upsampled
     patch-distance map.

Only the glue is written here; the heavy lifting is standard torch. Kept compact
on purpose — it is the swappable model, not the project's core contribution.
"""
from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import settings

# --- Lazy, guarded torch bootstrap ------------------------------------------


def _torch():
    import torch  # noqa: F401
    import torchvision  # noqa: F401
    return torch, torchvision


@functools.lru_cache(maxsize=1)
def _model():
    torch, tv = _torch()
    weights = tv.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1
    net = tv.models.wide_resnet50_2(weights=weights).eval()
    for p in net.parameters():
        p.requires_grad_(False)

    feats: dict = {}
    net.layer2.register_forward_hook(lambda m, i, o: feats.__setitem__("l2", o))
    net.layer3.register_forward_hook(lambda m, i, o: feats.__setitem__("l3", o))
    tf = weights.transforms()
    return net, feats, tf, torch


def _embed(image: Image.Image):
    net, feats, tf, torch = _model()
    x = tf(image.convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        net(x)
    l2, l3 = feats["l2"], feats["l3"]
    l3 = torch.nn.functional.interpolate(l3, size=l2.shape[-2:], mode="bilinear",
                                         align_corners=False)
    emb = torch.cat([l2, l3], dim=1)          # (1, C, H, W)
    _, c, h, w = emb.shape
    return emb.permute(0, 2, 3, 1).reshape(h * w, c), (h, w)


def _coreset(bank, n: int):
    """Greedy k-center coreset subsampling."""
    _, _, _, torch = _model()
    if bank.shape[0] <= n:
        return bank
    idx = [0]
    d = torch.cdist(bank, bank[idx])
    mins = d.min(dim=1).values
    for _ in range(n - 1):
        j = int(torch.argmax(mins))
        idx.append(j)
        mins = torch.minimum(mins, torch.cdist(bank, bank[j:j + 1]).squeeze(1))
    return bank[idx]


class PatchCore:
    def __init__(self, coreset_size: int = 4096):
        self.coreset_size = coreset_size
        self.bank = None
        self.grid = None

    def fit(self, train_good_dir: Path):
        _, _, _, torch = _model()
        embs = []
        for p in sorted(Path(train_good_dir).glob("*.png")):
            e, self.grid = _embed(Image.open(p))
            embs.append(e)
        bank = torch.cat(embs, dim=0)
        self.bank = _coreset(bank, self.coreset_size)
        return self

    def score_and_heatmap(self, image_id: str) -> dict:
        _, _, _, torch = _model()
        assert self.bank is not None, "call fit() first"
        root = settings.mvtec_root or Path(".")
        # image_id is expected like "<subset>/<file>.png" under the category.
        path = root / image_id
        img = Image.open(path)
        emb, (h, w) = _embed(img)
        d = torch.cdist(emb, self.bank).min(dim=1).values   # (h*w,)
        patch = d.reshape(h, w)
        score = float(patch.max())
        heat = torch.nn.functional.interpolate(
            patch[None, None], size=img.size[::-1], mode="bilinear",
            align_corners=False)[0, 0].cpu().numpy()
        heat = (heat - heat.min()) / (np.ptp(heat) + 1e-9)
        heat_rel = f"heatmaps/{Path(image_id).stem}.png"
        Image.fromarray((heat * 255).astype(np.uint8)).save(settings.data_dir / heat_rel)
        return {"score": round(score, 4), "image": image_id, "heatmap": heat_rel,
                "backend": "patchcore"}
