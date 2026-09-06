"""poseidon-lite forward shapes, parameter budget, and the masked training loss."""
import torch
import yaml

from model.lite import Lite
from model.losses import lite_loss

LITE_CFG = yaml.safe_load(open("configs/lite.yaml"))
TINY_CFG = yaml.safe_load(open("configs/tiny.yaml"))


def _build(cfg, window=None):
    return Lite(
        window or cfg["window"],
        12,
        cfg["width"],
        cfg["decoder_width"],
        cfg["emb_dim"],
        cfg["attn_heads"],
        cfg["depth_tokens"],
    )


def test_forward_shapes_at_two_sizes():
    model = _build(TINY_CFG)
    for h, w in [(16, 16), (24, 32)]:
        x = torch.randn(2, TINY_CFG["window"], 12, h, w)
        s = torch.randn(2, 3, h, w)
        mean, logsigma, emb = model(x, s)
        assert mean.shape == (2, 15, h, w)
        assert logsigma.shape == (2, 15, h, w)
        assert emb.shape[0] == 2 and emb.shape[1] == TINY_CFG["emb_dim"]


def test_lite_param_count_between_0p1m_and_0p4m():
    model = _build(LITE_CFG)
    n = sum(p.numel() for p in model.parameters())
    assert 100_000 <= n <= 400_000


def test_tiny_param_count_is_smaller_than_lite():
    lite_n = sum(p.numel() for p in _build(LITE_CFG).parameters())
    tiny_n = sum(p.numel() for p in _build(TINY_CFG).parameters())
    assert tiny_n < lite_n


def test_loss_decreases_on_one_batch():
    torch.manual_seed(0)
    model = _build(TINY_CFG)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-2)
    B, H, W = 2, 16, 16
    x = torch.randn(B, TINY_CFG["window"], 12, H, W)
    s = torch.randn(B, 3, H, W)
    y = torch.randn(B, 15, H, W)
    mask = torch.ones(B, 15, H, W)
    core = torch.ones(B, H, W)

    mean, logsigma, _ = model(x, s)
    loss0, _ = lite_loss(mean, logsigma, y, mask, core, TINY_CFG["loss"])
    for _ in range(20):
        opt.zero_grad()
        mean, logsigma, _ = model(x, s)
        loss, _ = lite_loss(mean, logsigma, y, mask, core, TINY_CFG["loss"])
        loss.backward()
        opt.step()
    mean, logsigma, _ = model(x, s)
    loss_final, _ = lite_loss(mean, logsigma, y, mask, core, TINY_CFG["loss"])
    assert float(loss_final.detach()) < float(loss0.detach())


def test_depth_head_output_varies_with_depth():
    """With real per-pixel keys/values, different depth queries must not collapse to the same field."""
    torch.manual_seed(0)
    model = _build(TINY_CFG)
    x = torch.randn(2, TINY_CFG["window"], 12, 16, 16)
    s = torch.randn(2, 3, 16, 16)
    mean, _, _ = model(x, s)
    diff = mean[:, 0] - mean[:, 14]
    assert diff.std().item() > 0


def test_depth_head_learns_anticorrelated_depths():
    """A short fit on anti-correlated depth-0/depth-14 targets should recover that anti-correlation."""
    torch.manual_seed(0)
    model = _build(TINY_CFG)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-2)
    B, H, W = 4, 16, 16
    x = torch.randn(B, TINY_CFG["window"], 12, H, W)
    s = torch.randn(B, 3, H, W)
    base = torch.randn(B, H, W)
    y = torch.zeros(B, 15, H, W)
    y[:, 0] = base
    y[:, 14] = -base
    # supervise only depths 0 and 14 so the other 13 (trivially zero) don't dilute the signal
    mask = torch.zeros(B, 15, H, W)
    mask[:, 0] = 1
    mask[:, 14] = 1
    core = torch.ones(B, H, W)

    for _ in range(600):
        opt.zero_grad()
        mean, logsigma, _ = model(x, s)
        loss, _ = lite_loss(mean, logsigma, y, mask, core, TINY_CFG["loss"])
        loss.backward()
        opt.step()

    mean, _, _ = model(x, s)
    d0, d14 = mean[:, 0].flatten(), mean[:, 14].flatten()
    corr = torch.corrcoef(torch.stack([d0, d14]))[0, 1]
    assert corr.item() < -0.3


def test_masked_cells_do_not_affect_loss():
    torch.manual_seed(1)
    model = _build(TINY_CFG)
    B, H, W = 1, 16, 16
    x = torch.randn(B, TINY_CFG["window"], 12, H, W)
    s = torch.randn(B, 3, H, W)
    y = torch.randn(B, 15, H, W)
    core = torch.ones(B, H, W)

    mean, logsigma, _ = model(x, s)
    mask_all = torch.ones(B, 15, H, W)
    mask_half = mask_all.clone()
    mask_half[:, :, H // 2 :, :] = 0.0  # mask out half the domain

    y_perturbed = y.clone()
    y_perturbed[:, :, H // 2 :, :] += 100.0  # garbage in the masked-out half

    loss_all, _ = lite_loss(mean, logsigma, y, mask_half, core, TINY_CFG["loss"])
    loss_perturbed, _ = lite_loss(mean, logsigma, y_perturbed, mask_half, core, TINY_CFG["loss"])
    assert float(loss_all.detach()) == float(loss_perturbed.detach())
