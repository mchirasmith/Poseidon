"""poseidon-lite: CNN encoder/decoder with a per-depth cross-attention head.

forward() requires H and W to be multiples of 8; pad with dataset.pad_to_multiple first.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

from pipeline.sources import DEPTHS_M

N_DEPTH = len(DEPTHS_M)


def _groups(c: int) -> int:
    for g in (8, 4, 2, 1):
        if c % g == 0:
            return g
    return 1


def _dwsep_conv(c: int) -> nn.Sequential:
    """Depthwise 3x3 + pointwise 1x1, to keep the ~0.2M param budget at wide channel counts."""
    return nn.Sequential(nn.Conv2d(c, c, 3, padding=1, groups=c), nn.Conv2d(c, c, 1))


LOGSIGMA_BOUND = 4.0  # sigma stays within e^-4 .. e^4 normalised units, with gradient everywhere
COAST_DISTANCE_CHANNEL = 2
COAST_DISTANCE_SCALE_KM = 1000.0

class ResBlock(nn.Module):
    def __init__(self, c: int):
        super().__init__()
        self.norm1 = nn.GroupNorm(_groups(c), c)
        self.conv1 = _dwsep_conv(c)
        self.norm2 = nn.GroupNorm(_groups(c), c)
        self.conv2 = _dwsep_conv(c)
        self.act = nn.SiLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.conv1(self.act(self.norm1(x)))
        h = self.conv2(self.act(self.norm2(h)))
        return x + h


class DepthAttnHead(nn.Module):
    """15 learned depth queries cross-attend over `depth_tokens` per-pixel keys/values; outputs mean, log-sigma."""

    def __init__(self, in_dim: int, d: int, heads: int, depth_tokens: int, n_depth: int = N_DEPTH, chunk: int = 0):
        super().__init__()
        self.d, self.heads, self.depth_tokens, self.chunk = d, heads, depth_tokens, chunk
        # The 15 queries are identical for every pixel, so they are stored already projected per head.
        self.kv_proj = nn.Conv2d(in_dim, 2 * depth_tokens * d, 1)
        self.query = nn.Parameter(torch.randn(heads, n_depth, d // heads) * 0.02)
        self.out_proj = nn.Linear(d, d)
        self.mean_head = nn.Linear(d, 1)
        self.logsigma_head = nn.Linear(d, 1)
        self.mean_bias = nn.Parameter(torch.zeros(n_depth))
        self.logsigma_bias = nn.Parameter(torch.zeros(n_depth))

    def _attend(self, kv: torch.Tensor) -> torch.Tensor:
        """(n, 2, heads, tokens, dh) keys/values -> (n, n_depth, 2) mean and log-sigma before the depth biases."""
        q = self.query.unsqueeze(0).expand(kv.shape[0], -1, -1, -1)
        ctx = F.scaled_dot_product_attention(q, kv[:, 0], kv[:, 1])
        ctx = self.out_proj(ctx.transpose(1, 2).reshape(kv.shape[0], -1, self.d))
        return torch.cat([self.mean_head(ctx), self.logsigma_head(ctx)], dim=-1)

    def forward(self, latent: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        B, C, H, W = latent.shape
        N, dh = B * H * W, self.d // self.heads
        kv = self.kv_proj(latent).permute(0, 2, 3, 1).reshape(N, 2, self.heads, self.depth_tokens, dh)
        if self.training and 0 < self.chunk < N:
            # Recomputing each pixel chunk in backward keeps only one chunk's attention activations alive.
            out = torch.cat([checkpoint(self._attend, kv[i : i + self.chunk], use_reentrant=False) for i in range(0, N, self.chunk)])
        else:
            out = self._attend(kv)
        mean = (out[..., 0] + self.mean_bias).reshape(B, H, W, -1).permute(0, 3, 1, 2)
        logsigma = (out[..., 1] + self.logsigma_bias).reshape(B, H, W, -1).permute(0, 3, 1, 2)
        # smooth bound: a hard clamp stops the gradient once sigma has blown up and the head never recovers
        logsigma = LOGSIGMA_BOUND * torch.tanh(logsigma / LOGSIGMA_BOUND)
        return mean, logsigma


class Lite(nn.Module):
    def __init__(
        self,
        window: int,
        in_channels_per_day: int,
        width,
        decoder_width,
        emb_dim,
        attn_heads,
        depth_tokens: int,
        static_channels: int = 3,
        head_chunk: int = 0,
    ):
        super().__init__()
        c_in = window * in_channels_per_day
        w0, w1, w2 = width
        dw0, dw1 = decoder_width

        # static channels are (wet, bottom depth / max depth, coast distance in km); the last one is O(1000)
        static_scale = torch.ones(static_channels)
        static_scale[COAST_DISTANCE_CHANNEL] = 1.0 / COAST_DISTANCE_SCALE_KM
        self.register_buffer("static_scale", static_scale.view(1, -1, 1, 1))
        self.stem = nn.Sequential(nn.Conv2d(c_in, w0, 3, padding=1), nn.GroupNorm(_groups(w0), w0), nn.SiLU())
        self.enc1 = nn.Sequential(ResBlock(w0), ResBlock(w0))
        self.down1 = nn.Conv2d(w0, w1, 3, stride=2, padding=1)
        self.enc2 = nn.Sequential(ResBlock(w1), ResBlock(w1))
        self.down2 = nn.Conv2d(w1, w2, 3, stride=2, padding=1)
        self.enc3 = nn.Sequential(ResBlock(w2), ResBlock(w2))
        self.to_emb = nn.Conv2d(w2, emb_dim, 1)

        self.dec1 = nn.Conv2d(emb_dim + w1, dw0, 3, padding=1)
        self.dec2 = nn.Conv2d(dw0 + w0, dw1, 3, padding=1)
        self.dec_act = nn.SiLU()

        latent_dim = dw1 + static_channels
        self.head = DepthAttnHead(latent_dim, dw1, attn_heads, depth_tokens, chunk=head_chunk)

    def forward(self, x: torch.Tensor, static: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        B, k, c, H, W = x.shape
        assert H % 8 == 0 and W % 8 == 0, "Lite.forward requires H and W to be multiples of 8"
        x = x.reshape(B, k * c, H, W)

        s0 = self.enc1(self.stem(x))
        s1 = self.enc2(self.down1(s0))
        e2 = self.enc3(self.down2(s1))
        embedding = self.to_emb(e2)

        u1 = F.interpolate(embedding, size=s1.shape[-2:], mode="bilinear", align_corners=False)
        u1 = self.dec_act(self.dec1(torch.cat([u1, s1], dim=1)))

        u2 = F.interpolate(u1, size=s0.shape[-2:], mode="bilinear", align_corners=False)
        u2 = self.dec_act(self.dec2(torch.cat([u2, s0], dim=1)))

        latent = torch.cat([u2, static * self.static_scale], dim=1)
        mean, logsigma = self.head(latent)
        return mean, logsigma, embedding
