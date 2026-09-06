"""poseidon-lite: CNN encoder/decoder with a per-depth cross-attention head.

forward() requires H and W to be multiples of 8; pad with dataset.pad_to_multiple first.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

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

    def __init__(self, in_dim: int, d: int, heads: int, depth_tokens: int, n_depth: int = N_DEPTH):
        super().__init__()
        self.d = d
        self.depth_tokens = depth_tokens
        self.kv_proj = nn.Conv2d(in_dim, depth_tokens * d, 1)
        self.depth_query = nn.Parameter(torch.randn(n_depth, d) * 0.02)
        self.attn = nn.MultiheadAttention(d, heads, batch_first=True)
        self.mean_head = nn.Linear(2 * d, 1)
        self.logsigma_head = nn.Linear(2 * d, 1)

    def forward(self, latent: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        B, C, H, W = latent.shape
        kv = self.kv_proj(latent).permute(0, 2, 3, 1).reshape(B * H * W, self.depth_tokens, self.d)
        q = self.depth_query.unsqueeze(0).expand(B * H * W, -1, -1)
        ctx, _ = self.attn(q, kv, kv)
        combo = torch.cat([ctx, q], dim=-1)
        mean = self.mean_head(combo).squeeze(-1).reshape(B, H, W, -1).permute(0, 3, 1, 2)
        logsigma = self.logsigma_head(combo).squeeze(-1).reshape(B, H, W, -1).permute(0, 3, 1, 2)
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
    ):
        super().__init__()
        c_in = window * in_channels_per_day
        w0, w1, w2 = width
        dw0, dw1 = decoder_width

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
        self.head = DepthAttnHead(latent_dim, dw1, attn_heads, depth_tokens)

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

        latent = torch.cat([u2, static], dim=1)
        mean, logsigma = self.head(latent)
        return mean, logsigma, embedding
