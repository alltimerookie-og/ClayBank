# ADR 0008 — On-device inference is CPU-only (and why: MediaTek, virtual RAM, benchmarks)

**Status:** Accepted (backend implementation now; on-device build is post-hackathon item 1) · **Date:** 2026-10-31

## Context

The user wants **local chat inside the app with no external dependency** — no Ollama daemon, no user-installed server — and asked whether virtual RAM or GPU/NPU acceleration would help. The 8 GB-RAM demo phone is **MediaTek**. Wheels on `pypi.flet.dev` (`llama_cpp_python 0.3.32`, `onnxruntime 1.27.0`, `faiss-cpu`, `flet-libffmpeg`) prove in-process inference is possible in Flet, so the honest engineering question is *which accelerator in what scope*.

## Findings (measured, not vibes)

| Path | Measured result |
|---|---|
| CPU (NEON) | 1B Q4: ~14 t/s · 1.5B Q4: ~15 t/s · 2B Q4: ~6–10 t/s |
| **Vulkan (Adreno 830, flagship)** | 24× faster *prefill* (prompt read), **+2.7× faster token gen** for 1.5B; but **17 % slower** token gen for a 7B |
| **Vulkan (Adreno 720, mid-range)** | **3.5× slower than CPU** (4 vs 14 t/s, Llama 3.2 1B) |
| **Hexagon NPU (ggml-hexagon)** | requires Snapdragon 8 Gen 2+, only works with different quantization (Q4_0/IQ4_NL), and no MediaTek backend |
| **Virtual RAM (RAM Plus / ZRAM)** | **worse, not better** — token generation touches every weight per token; paging a 1.6 GB working set to flash collapses throughput and heats the phone. It only helps keep *other* apps alive. |

## Decision

- **CPU-only in the MVP**, pinned to 4 threads, `n_ctx 4096`, Q4_K_M weights, run as a **foreground service** so Android does not evict it mid-answer.
- **NPU is struck from the backlog** with the reason recorded: the demo device is MediaTek and there is no llama.cpp backend for it. Do not revive it for this device.
- GPU/Vulkan is a **post-hackathon, gate on measurement**: benchmark on the *actual* demo phone first (mid-range Mali is likely slower than CPU to generate, and the mega-adreno win is a flagship-only outlier).
- **Two local models ship, user-selected in Settings:** MiniCPM5-2B Q4_K_M (**1.56 GB**; best quality, EN/ZH only) and Qwen3-1.7B (**~1.1 GB**; genuinely multilingual). One is loaded at a time.
- **8 GB RAM floor documented** as the device requirement (model 0.7–1.6 GB + KV cache at 4k + Flet/Python + ONNX embeddings ≈ 2.7–3 GB app footprint; 6 GB devices thrash).
- Known limitations go into the docs, not into hopes: **no Bangla chat quality** on the MiniCPM path (its model card claims EN/ZH only; note generation stays cloud-only for a reason), **no GPU/NPU in MVP**, **no virtual-RAM reliance**.

## Rejected alternatives

- **Ollama daemon:** an external process the user must install — violates the "no external dependency" requirement; the interface stays runtime-agnostic anyway.
- **`transformers` + torch:** pulls ~2.5 GB of torch into an app whose whole pipeline avoids torch.
- **GPU in MVP:** custom wheel builds, Android toolchain detour, and mid-range measurement says *slower*.
- **Qat/quant experiments (QAT, MXFP4):** post-hackathon only, benchmarked.

## Consequences

- Local chat is a **"setting that works"**, not a demo path: CPU latency is ~6–10 t/s; a 300-token answer takes 30–50 s. UI shows *"running on device · slower"* and keeps cooking the answer without pretending it's instant.
- The `LocalProvider` interface (`backend.py first`, on-device later) is built now (`Architecture.md` §3/§5) so the post-hackathon task is a plug-in, not a redesign.
- Thermals risk nothing for the demo (cloud is default); it only matters on-device after the hackathon — which is why the benchmark gate exists before any accelerated build.
