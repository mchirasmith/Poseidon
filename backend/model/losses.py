"""Masked Gaussian NLL plus vertical-gradient Huber loss for poseidon-lite."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from pipeline.sources import DEPTHS_M

THERMOCLINE_MIN_M, THERMOCLINE_MAX_M = 50.0, 200.0


def depth_weights(device=None) -> torch.Tensor:
    """1.0 everywhere, thermocline_w applied later by the caller on the 50-200m band."""
    band = (DEPTHS_M >= THERMOCLINE_MIN_M) & (DEPTHS_M <= THERMOCLINE_MAX_M)
    return torch.as_tensor(band, dtype=torch.float32, device=device)


def masked_gaussian_nll(mean: torch.Tensor, logsigma: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Per-element diagonal Gaussian NLL, masked mean. All tensors (B, 15, H, W)."""
    logsigma = logsigma.clamp(-6.0, 6.0)
    sigma = torch.exp(logsigma)
    nll = 0.5 * np.log(2 * np.pi) + logsigma + 0.5 * ((target - mean) / sigma) ** 2
    denom = mask.sum().clamp(min=1.0)
    return (nll * mask).sum() / denom


def vgrad_huber(mean: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Huber loss on vertical differences T[z+1]-T[z] between adjacent standard depths."""
    d_pred = mean[:, 1:] - mean[:, :-1]
    d_true = target[:, 1:] - target[:, :-1]
    pair_mask = mask[:, 1:] * mask[:, :-1]
    huber = F.huber_loss(d_pred, d_true, reduction="none")
    denom = pair_mask.sum().clamp(min=1.0)
    return (huber * pair_mask).sum() / denom


def lite_loss(mean, logsigma, target, mask, core_mask, cfg: dict) -> tuple[torch.Tensor, dict]:
    """Combined loss with thermocline depth weighting; core_mask restricts the loss to each tile's core."""
    band = depth_weights(mean.device).view(1, -1, 1, 1)
    weight = 1.0 + (cfg["thermocline_w"] - 1.0) * band
    full_mask = mask * core_mask.unsqueeze(1) * weight

    nll = masked_gaussian_nll(mean, logsigma, target, full_mask)
    vgrad = vgrad_huber(mean, target, mask * core_mask.unsqueeze(1))
    total = cfg["nll"] * nll + cfg["vgrad"] * vgrad
    return total, {"nll": float(nll.detach()), "vgrad": float(vgrad.detach())}
