"""
IRONMARK — Native Hardware Benchmark
Requires: pip install psutil wmi pywin32 numpy gputil customtkinter
Optional:  pip install pyopencl  (for real GPU compute)
"""

import tkinter as tk
import customtkinter as ctk
import threading
import time
import math
import os
import sys
import platform
import multiprocessing
import random
import numpy as np
from datetime import datetime

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

try:
    import pyopencl as cl
    HAS_OPENCL = True
except ImportError:
    HAS_OPENCL = False

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG        = "#0d0d10"
SURFACE   = "#141418"
BORDER    = "#252530"
ACCENT    = "#00e87a"   # green  — CPU
ACCENT2   = "#ff3d5c"   # red    — SSD
ACCENT3   = "#3d8fff"   # blue   — GPU
ACCENT4   = "#ffa020"   # orange — RAM
MUTED     = "#4a4a60"
TEXT      = "#dcdce8"
MONO      = "Courier New"
SANS      = "Arial"

# ── Worker (top-level for multiprocessing) ────────────────────────────────────
def _worker_cpu_task(_):
    s = 0.0
    for i in range(4_000_000):
        s += math.sqrt(i * 3.14159 + 1.5) * math.log(i + 1)
    return s

# ── Hardware info ─────────────────────────────────────────────────────────────
def get_hw_info():
    info = {}

    # CPU
    info['cpu_name']           = platform.processor() or "Unknown CPU"
    info['cpu_cores_physical'] = psutil.cpu_count(logical=False) if HAS_PSUTIL else os.cpu_count() // 2
    info['cpu_cores_logical']  = psutil.cpu_count(logical=True)  if HAS_PSUTIL else os.cpu_count()
    info['cpu_freq_max']       = 0

    if HAS_PSUTIL:
        freq = psutil.cpu_freq()
        if freq:
            info['cpu_freq_max'] = round(freq.max / 1000, 2) if freq.max > 100 else round(freq.max, 2)

    if HAS_WMI:
        try:
            c = wmi.WMI()
            for cpu in c.Win32_Processor():
                info['cpu_name'] = cpu.Name.strip()
                if not info['cpu_freq_max']:
                    info['cpu_freq_max'] = round(cpu.MaxClockSpeed / 1000, 2)
                break
        except:
            pass

    # RAM
    info['ram_total_gb'] = 0
    info['ram_type']     = "DDR?"
    info['ram_speed']    = 0
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        info['ram_total_gb'] = round(vm.total / (1024 ** 3), 1)
    if HAS_WMI:
        try:
            c = wmi.WMI()
            sticks = list(c.Win32_PhysicalMemory())
            if sticks:
                info['ram_speed'] = sticks[0].Speed or 0
                mt = sticks[0].MemoryType or 0
                ft = sticks[0].SMBIOSMemoryType or 0
                if ft == 34 or mt == 30:   info['ram_type'] = "DDR5"
                elif ft == 26 or mt == 26: info['ram_type'] = "DDR4"
                elif ft == 24:             info['ram_type'] = "DDR3"
                else:                      info['ram_type'] = "DDR?"
        except:
            pass

    # GPU
    info['gpu_name']   = "Unknown GPU"
    info['gpu_vram']   = 0
    info['gpu_driver'] = ""
    if HAS_WMI:
        try:
            c = wmi.WMI()
            for gpu in c.Win32_VideoController():
                name = (gpu.Name or "").strip()
                if name and "basic" not in name.lower():
                    info['gpu_name']   = name
                    vram               = gpu.AdapterRAM or 0
                    info['gpu_vram']   = round(vram / (1024 ** 3), 1)
                    info['gpu_driver'] = gpu.DriverVersion or ""
                    break
        except:
            pass
    if HAS_GPUTIL and info['gpu_name'] == "Unknown GPU":
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                info['gpu_name'] = gpus[0].name
                info['gpu_vram'] = round(gpus[0].memoryTotal / 1024, 1)
        except:
            pass

    # Storage
    info['storage_path']     = "C:\\" if sys.platform == "win32" else "/"
    info['storage_total_gb'] = 0
    info['storage_type']     = "Unknown"
    if HAS_PSUTIL:
        try:
            du = psutil.disk_usage(info['storage_path'])
            info['storage_total_gb'] = round(du.total / (1024 ** 3), 0)
        except:
            pass
    if HAS_WMI:
        try:
            c = wmi.WMI()
            for disk in c.Win32_DiskDrive():
                mt    = (disk.MediaType or "").lower()
                model = (disk.Model or "").lower()
                if any(k in mt + model for k in ('ssd', 'solid', 'nvme', 'samsung')):
                    info['storage_type'] = "SSD/NVMe"
                elif any(k in mt for k in ('hdd', 'fixed')):
                    info['storage_type'] = "HDD"
                break
        except:
            pass

    info['os']   = platform.system() + " " + platform.release()
    info['arch'] = platform.machine()
    return info


# ── GPU tier lookup ───────────────────────────────────────────────────────────
def _gpu_tier_score(name: str) -> int:
    n = name.lower()
    tiers = [
        (['4090', '4080', '4070 ti', '3090 ti', '7900 xtx'],        9800),
        (['3090', '6900 xt', '7900 xt'],                             9200),
        (['4070 super', '4070', '3080 ti', '6800 xt', '7800 xt'],    8500),
        (['3080', '4060 ti', '6800', '7700 xt'],                     7800),
        (['3070 ti', '6750 xt', '4060'],                             7000),
        (['3070', '6700 xt', '2080 ti'],                             6500),
        (['3060 ti', '2080', '6700'],                                6000),
        (['3060', '2070 super', '6600 xt'],                          5500),
        (['2070', '6600', '3050 ti'],                                5000),
        (['2060 super', '5700'],                                     4500),
        (['2060', '3050', '1080 ti', '6500 xt'],                     4000),
        (['1080', '1070 ti', '5600 xt'],                             3500),
        (['1070', '1660 super', '1660 ti'],                          3000),
        (['1660', '2060', 'rx 580', 'rx 5500'],                      2500),
        (['1060', '1650 super', 'rx 570'],                           2000),
        (['1650', '1050 ti', 'rx 560'],                              1500),
        (['iris', 'uhd', 'integrated', 'vega', 'radeon graphics'],    800),
    ]
    for keywords, score in tiers:
        if any(k in n for k in keywords):
            return score
    return 2000  # default unknown


# ── Benchmarks ────────────────────────────────────────────────────────────────
def bench_cpu(progress_cb, log_cb):
    cores = multiprocessing.cpu_count()
    R = {}

    log_cb("[CPU] Single-thread: Решето Эратосфена...")
    progress_cb(5)
    t = time.perf_counter()
    N = 3_000_000
    sieve = bytearray([1]) * (N + 1)
    sieve[0] = sieve[1] = 0
    i = 2
    while i * i <= N:
        if sieve[i]:
            sieve[i * i::i] = bytes(len(sieve[i * i::i]))
        i += 1
    prime_time = time.perf_counter() - t
    R['prime'] = min(10000, int(150000 / prime_time))
    log_cb(f"[CPU] Prime: {prime_time*1000:.0f}ms → {R['prime']} pts")
    progress_cb(20)

    log_cb("[CPU] Single-thread: Float Math (numpy)...")
    t = time.perf_counter()
    arr = np.arange(1, 5_000_001, dtype=np.float64)
    _ = np.sum(np.sin(arr * 0.001) * np.cos(arr * 0.002) + np.sqrt(arr))
    float_time = time.perf_counter() - t
    R['float'] = min(10000, int(8000 / float_time))
    log_cb(f"[CPU] Float: {float_time*1000:.0f}ms → {R['float']} pts")
    progress_cb(35)

    log_cb("[CPU] Single-thread: Integer / Bitwise XOR...")
    t = time.perf_counter()
    x = 0x12345678
    for i in range(10_000_000):
        x = (x ^ (i * 0x9E3779B9)) & 0xFFFFFFFF
    bw_time = time.perf_counter() - t
    R['bitwise'] = min(10000, int(60000 / bw_time))
    log_cb(f"[CPU] Bitwise: {bw_time*1000:.0f}ms → {R['bitwise']} pts")
    progress_cb(50)

    log_cb("[CPU] Single-thread: Matrix Multiply 512×512 (numpy)...")
    t = time.perf_counter()
    A = np.random.rand(512, 512).astype(np.float64)
    B = np.random.rand(512, 512).astype(np.float64)
    for _ in range(5):
        C = np.dot(A, B)
    mat_time = time.perf_counter() - t
    gflops = (5 * 2 * 512 ** 3) / mat_time / 1e9
    R['matrix'] = min(10000, int(gflops * 120))
    log_cb(f"[CPU] Matrix: {mat_time*1000:.0f}ms, {gflops:.2f} GFLOPS → {R['matrix']} pts")
    progress_cb(65)

    log_cb(f"[CPU] Multi-thread: {cores} cores...")
    t = time.perf_counter()
    with multiprocessing.Pool(processes=cores) as pool:
        pool.map(_worker_cpu_task, range(cores))
    mt_time = time.perf_counter() - t
    R['multi'] = min(10000, int((cores * 25000) / mt_time))
    log_cb(f"[CPU] Multi: {mt_time*1000:.0f}ms → {R['multi']} pts")
    progress_cb(100)

    st = int((R['prime'] + R['float'] + R['bitwise'] + R['matrix']) / 4)
    final = min(10000, int(
        R['prime']  * 0.15 + R['float']  * 0.20 +
        R['bitwise']* 0.10 + R['matrix'] * 0.20 + R['multi'] * 0.35
    ))
    details = {
        'Single-thread': st,
        'Multi-thread':  R['multi'],
        'Prime Sieve':   R['prime'],
        'Float Math':    R['float'],
        'Matrix GEMM':   R['matrix'],
        'Bitwise Ops':   R['bitwise'],
    }
    return final, details


def bench_gpu(progress_cb, log_cb):
    """
    Real GPU benchmark via OpenCL if available.
    Falls back to CPU-proxy (numpy GEMM) with clear labelling.
    """
    R = {}
    gpu_name = "Unknown GPU"

    # --- Detect GPU name & tier score ---
    if HAS_WMI:
        try:
            c = wmi.WMI()
            for gpu in c.Win32_VideoController():
                name = (gpu.Name or "").strip()
                if name and "basic" not in name.lower():
                    gpu_name = name
                    break
        except:
            pass
    if HAS_GPUTIL and gpu_name == "Unknown GPU":
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_name = gpus[0].name
        except:
            pass

    tier_score = _gpu_tier_score(gpu_name)
    log_cb(f"[GPU] Detected: {gpu_name}  tier={tier_score}")
    progress_cb(10)

    # --- Real OpenCL path ---
    opencl_score = None
    opencl_note  = ""
    if HAS_OPENCL:
        try:
            platforms = cl.get_platforms()
            gpu_devices = []
            for p in platforms:
                try:
                    gpu_devices += p.get_devices(device_type=cl.device_type.GPU)
                except:
                    pass

            if gpu_devices:
                dev = gpu_devices[0]
                ctx = cl.Context([dev])
                queue = cl.CommandQueue(ctx)

                N = 1024
                kernel_src = """
                __kernel void sgemm(
                    __global const float* A,
                    __global const float* B,
                    __global       float* C,
                    int N)
                {
                    int row = get_global_id(0);
                    int col = get_global_id(1);
                    float sum = 0.0f;
                    for (int k = 0; k < N; k++)
                        sum += A[row*N + k] * B[k*N + col];
                    C[row*N + col] = sum;
                }
                """
                prg  = cl.Program(ctx, kernel_src).build()
                mf   = cl.mem_flags
                A_np = np.random.rand(N, N).astype(np.float32)
                B_np = np.random.rand(N, N).astype(np.float32)
                C_np = np.zeros((N, N), dtype=np.float32)
                A_g  = cl.Buffer(ctx, mf.READ_ONLY  | mf.COPY_HOST_PTR, hostbuf=A_np)
                B_g  = cl.Buffer(ctx, mf.READ_ONLY  | mf.COPY_HOST_PTR, hostbuf=B_np)
                C_g  = cl.Buffer(ctx, mf.WRITE_ONLY, C_np.nbytes)

                log_cb("[GPU] OpenCL SGEMM 1024×1024 warmup...")
                prg.sgemm(queue, (N, N), None, A_g, B_g, C_g, np.int32(N))
                queue.finish()
                progress_cb(30)

                RUNS = 10
                log_cb(f"[GPU] OpenCL SGEMM ×{RUNS}...")
                t = time.perf_counter()
                for _ in range(RUNS):
                    prg.sgemm(queue, (N, N), None, A_g, B_g, C_g, np.int32(N))
                queue.finish()
                elapsed = time.perf_counter() - t
                gflops = (RUNS * 2 * N ** 3) / elapsed / 1e9
                opencl_score = min(9000, int(gflops * 8))
                opencl_note  = f"{gflops:.1f} GFLOPS (OpenCL)"
                log_cb(f"[GPU] OpenCL: {gflops:.1f} GFLOPS → {opencl_score} pts")
                progress_cb(60)

                # Bandwidth test
                log_cb("[GPU] OpenCL memory bandwidth...")
                SIZE = 64 * 1024 * 1024 // 4  # 64 MB float32
                src_np = np.ones(SIZE, dtype=np.float32)
                dst_np = np.zeros(SIZE, dtype=np.float32)
                src_g  = cl.Buffer(ctx, mf.READ_ONLY  | mf.COPY_HOST_PTR, hostbuf=src_np)
                dst_g  = cl.Buffer(ctx, mf.WRITE_ONLY, dst_np.nbytes)
                bw_kernel_src = """
                __kernel void copy(__global const float* src, __global float* dst) {
                    int i = get_global_id(0);
                    dst[i] = src[i];
                }
                """
                bw_prg = cl.Program(ctx, bw_kernel_src).build()
                BWRUNS = 20
                t = time.perf_counter()
                for _ in range(BWRUNS):
                    bw_prg.copy(queue, (SIZE,), None, src_g, dst_g)
                queue.finish()
                bw_elapsed = time.perf_counter() - t
                bw_gb = (BWRUNS * SIZE * 4 * 2) / bw_elapsed / 1e9
                bw_score = min(10000, int(bw_gb * 30))
                R['bw_score'] = bw_score
                log_cb(f"[GPU] BW: {bw_gb:.1f} GB/s → {bw_score} pts")
                progress_cb(80)

        except Exception as e:
            log_cb(f"[GPU] OpenCL error: {e}")

    # Fallback / supplement: numpy GEMM (CPU proxy)
    log_cb("[GPU] CPU-side GEMM proxy (supplement)...")
    N2 = 1024
    A2 = np.random.rand(N2, N2).astype(np.float32)
    B2 = np.random.rand(N2, N2).astype(np.float32)
    RUNS2 = 15
    t = time.perf_counter()
    for _ in range(RUNS2):
        _ = np.dot(A2, B2)
    elapsed2 = time.perf_counter() - t
    gflops2 = (RUNS2 * 2 * N2 ** 3) / elapsed2 / 1e9
    cpu_proxy_score = min(5000, int(gflops2 * 50))
    R['cpu_proxy'] = cpu_proxy_score
    log_cb(f"[GPU] CPU proxy: {gflops2:.1f} GFLOPS → {cpu_proxy_score} pts")
    progress_cb(90)

    # Texture fill
    log_cb("[GPU] Texture fill simulation...")
    SIZE_T = 2048
    buf = np.zeros((SIZE_T, SIZE_T, 4), dtype=np.uint8)
    t = time.perf_counter()
    for i in range(10):
        buf[:, :, 0] = np.random.randint(0, 256, (SIZE_T, SIZE_T), dtype=np.uint8)
        buf[:, :, 1] = np.roll(buf[:, :, 0], i * 17)
        buf[:, :, 2] = np.flip(buf[:, :, 0])
    fill_time = time.perf_counter() - t
    fill_bw   = (10 * SIZE_T * SIZE_T * 4) / fill_time / (1024 ** 2)
    fill_score = min(10000, int(fill_bw * 5))
    R['fill'] = fill_score
    log_cb(f"[GPU] Fill: {fill_bw:.0f} MB/s → {fill_score} pts")
    progress_cb(100)

    # Compose final score
    if opencl_score is not None:
        # Real GPU path: tier(50%) + opencl(30%) + bw(10%) + fill(10%)
        bw_s = R.get('bw_score', 2000)
        final = min(10000, int(
            tier_score  * 0.50 +
            opencl_score* 0.30 +
            bw_s        * 0.10 +
            fill_score  * 0.10
        ))
        mode_note = "OpenCL ✓"
    else:
        # CPU-proxy fallback: tier(60%) + proxy(25%) + fill(15%)
        final = min(10000, int(
            tier_score     * 0.60 +
            cpu_proxy_score* 0.25 +
            fill_score     * 0.15
        ))
        mode_note = "CPU proxy (install pyopencl for real GPU test)"

    details = {
        'GPU':          gpu_name[:32],
        'Tier Score':   tier_score,
        'Mode':         mode_note,
    }
    if opencl_score is not None:
        details['OpenCL GFLOPS'] = opencl_note
        details['BW Score']      = R.get('bw_score', 0)
    else:
        details['CPU Proxy Sc.'] = cpu_proxy_score
    details['Fill Score'] = fill_score

    return final, details


def bench_ram(progress_cb, log_cb):
    R = {}
    MB = 1024 * 1024
    SIZE = 256 * MB // 8

    log_cb("[RAM] Sequential Write 256 MB...")
    progress_cb(10)
    arr = np.empty(SIZE, dtype=np.float64)
    t = time.perf_counter()
    arr[:] = 3.14159265
    np.copyto(arr, np.full(SIZE, 2.71828))
    wt = time.perf_counter() - t
    wbw = (SIZE * 8 * 2) / wt / MB
    R['write'] = min(10000, int(wbw * 2.5))
    log_cb(f"[RAM] Write: {wbw:.0f} MB/s → {R['write']} pts")
    progress_cb(35)

    log_cb("[RAM] Sequential Read 256 MB...")
    t = time.perf_counter()
    _ = np.sum(arr); _ = np.sum(arr)
    rt = time.perf_counter() - t
    rbw = (SIZE * 8 * 2) / rt / MB
    R['read'] = min(10000, int(rbw * 2.5))
    log_cb(f"[RAM] Read: {rbw:.0f} MB/s → {R['read']} pts")
    progress_cb(60)

    log_cb("[RAM] Latency (pointer chasing 4 MB)...")
    LSIZE = 4 * 1024 * 1024 // 4
    lbuf = np.arange(LSIZE, dtype=np.uint32)
    np.random.shuffle(lbuf)
    ITERS = 2_000_000
    t = time.perf_counter()
    idx = 0
    for _ in range(ITERS):
        idx = lbuf[idx % LSIZE]
    lat_ns = (time.perf_counter() - t) * 1e9 / ITERS
    R['latency'] = min(10000, int(200 / lat_ns * 1000))
    log_cb(f"[RAM] Latency: {lat_ns:.1f} ns → {R['latency']} pts")
    progress_cb(80)

    log_cb("[RAM] Copy Bandwidth 128 MB...")
    CSIZE = 128 * MB // 8
    src = np.random.rand(CSIZE).astype(np.float64)
    dst = np.empty(CSIZE, dtype=np.float64)
    t = time.perf_counter()
    np.copyto(dst, src); np.copyto(dst, src)
    ct = time.perf_counter() - t
    cbw = (CSIZE * 8 * 2) / ct / MB
    R['copy'] = min(10000, int(cbw * 2))
    log_cb(f"[RAM] Copy: {cbw:.0f} MB/s → {R['copy']} pts")
    progress_cb(100)

    final = min(10000, int(
        R['write']   * 0.30 + R['read']    * 0.30 +
        R['latency'] * 0.25 + R['copy']    * 0.15
    ))
    details = {
        'Read BW':       f"{rbw:.0f} MB/s",
        'Write BW':      f"{wbw:.0f} MB/s",
        'Latency':       f"{lat_ns:.1f} ns",
        'Copy BW':       f"{cbw:.0f} MB/s",
        'Read Score':    R['read'],
        'Write Score':   R['write'],
        'Latency Score': R['latency'],
        'Copy Score':    R['copy'],
    }
    return final, details


def bench_storage(progress_cb, log_cb):
    R = {}
    MB   = 1024 * 1024
    path = os.path.join(os.path.expanduser("~"), "_ironmark_bench_tmp")

    log_cb("[SSD] Sequential Write 512 MB...")
    progress_cb(10)
    CHUNK = 1 * MB
    COUNT = 512
    data  = os.urandom(CHUNK)
    t = time.perf_counter()
    with open(path, "wb") as f:
        for _ in range(COUNT):
            f.write(data)
        f.flush()
        os.fsync(f.fileno())
    wt = time.perf_counter() - t
    wbw = (COUNT * CHUNK) / wt / MB
    R['write'] = min(10000, int(wbw * 2.5))
    log_cb(f"[SSD] Write: {wbw:.0f} MB/s → {R['write']} pts")
    progress_cb(40)

    log_cb("[SSD] Sequential Read 512 MB...")
    t = time.perf_counter()
    with open(path, "rb") as f:
        while f.read(CHUNK):
            pass
    rt = time.perf_counter() - t
    rbw = (COUNT * CHUNK) / rt / MB
    R['read'] = min(10000, int(rbw * 2.0))
    log_cb(f"[SSD] Read: {rbw:.0f} MB/s → {R['read']} pts")
    progress_cb(70)

    log_cb("[SSD] Random 4K IOPS (3 sec)...")
    fsize = os.path.getsize(path)
    BLOCK = 4096
    count = 0
    t = time.perf_counter()
    with open(path, "rb") as f:
        deadline = t + 3.0
        while time.perf_counter() < deadline:
            offset = (random.randint(0, max(0, fsize - BLOCK)) // BLOCK) * BLOCK
            f.seek(offset)
            f.read(BLOCK)
            count += 1
    iops = int(count / (time.perf_counter() - t))
    R['iops'] = min(10000, int(iops * 0.8))
    log_cb(f"[SSD] 4K IOPS: {iops} → {R['iops']} pts")
    progress_cb(90)

    try:
        os.remove(path)
    except:
        pass

    progress_cb(100)
    final = min(10000, int(R['write'] * 0.40 + R['read'] * 0.35 + R['iops'] * 0.25))
    details = {
        'Seq Write':   f"{wbw:.0f} MB/s",
        'Seq Read':    f"{rbw:.0f} MB/s",
        '4K IOPS':     f"{iops}",
        'Write Score': R['write'],
        'Read Score':  R['read'],
        'IOPS Score':  R['iops'],
    }
    return final, details


# ── Grade ─────────────────────────────────────────────────────────────────────
def get_grade(score):
    if score >= 9000: return "S", ACCENT,   "FLAGSHIP — Топовое железо"
    if score >= 7500: return "A", "#40e080", "HIGH-END — Мощная система"
    if score >= 6000: return "B", "#80c040", "MID-HIGH — Хорошая производительность"
    if score >= 4500: return "C", ACCENT4,   "MIDRANGE — Для большинства задач"
    if score >= 3000: return "D", "#ff6030", "ENTRY LEVEL — Бюджетный класс"
    return                   "F", ACCENT2,   "LOW-END — Рекомендуется апгрейд"


# ── Logo canvas widget ─────────────────────────────────────────────────────────
class LogoCanvas(tk.Canvas):
    """Sharp geometric SVG-style logo drawn with tk.Canvas."""

    def __init__(self, parent, **kw):
        super().__init__(parent, width=200, height=40,
                         bg=SURFACE, highlightthickness=0, **kw)
        self._draw()

    def _draw(self):
        # "⬡ IRONMARK" — hexagon accent + text
        # Draw small hexagon
        cx, cy, r = 18, 20, 11
        pts = []
        for i in range(6):
            ang = math.radians(60 * i - 30)
            pts += [cx + r * math.cos(ang), cy + r * math.sin(ang)]
        self.create_polygon(pts, outline=ACCENT, fill="", width=2)
        # inner dot
        self.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=ACCENT, outline="")
        # IRON in white
        self.create_text(38, 20, text="IRON", anchor="w",
                         font=(SANS, 18, "bold"), fill=TEXT)
        # MARK in accent green
        self.create_text(90, 20, text="MARK", anchor="w",
                         font=(SANS, 18, "bold"), fill=ACCENT)
        # thin separator line underneath
        self.create_line(0, 39, 200, 39, fill=BORDER, width=1)


# ── App ────────────────────────────────────────────────────────────────────────
class IronmarkApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IRONMARK — Hardware Benchmark")
        self.geometry("860x740")
        self.minsize(800, 660)
        self.configure(fg_color=BG)
        self.resizable(True, True)
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            self.iconbitmap(os.path.join(base, "icon.ico"))
        except Exception:
            pass

        self.scores  = {"cpu": 0, "gpu": 0, "ram": 0, "storage": 0}
        self.running = False
        self.hw      = {}

        self._build_ui()
        self._detect_hw()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ─────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, border_width=0)
        hdr.pack(fill="x")
        inner = ctk.CTkFrame(hdr, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=12)

        LogoCanvas(inner).pack(side="left")

        tag = ctk.CTkLabel(inner, text="Native Hardware Benchmark  v2.1",
                           font=(MONO, 10), text_color=MUTED)
        tag.pack(side="left", padx=16, pady=(4, 0))

        # ── Scroll body ────────────────────────
        body = ctk.CTkScrollableFrame(self, fg_color=BG, scrollbar_button_color=BORDER)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        P = {"padx": 18, "pady": (8, 0)}

        # ── HW panel ───────────────────────────
        hw_f = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=3,
                             border_color=BORDER, border_width=1)
        hw_f.pack(fill="x", **P)
        ctk.CTkLabel(hw_f, text="DETECTED HARDWARE",
                     font=(MONO, 8), text_color=MUTED).pack(anchor="w", padx=14, pady=(8, 4))

        grid = ctk.CTkFrame(hw_f, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 10))

        self.hw_labels = {}
        fields = [
            ("CPU",     "cpu_name"), ("Cores", "cores"),
            ("GPU",     "gpu_name"), ("VRAM",  "gpu_vram"),
            ("RAM",     "ram"),      ("Type",  "ram_type"),
            ("Storage", "storage"),  ("OS",    "os"),
        ]
        for i, (label, key) in enumerate(fields):
            col, row = i % 4, i // 4
            f = ctk.CTkFrame(grid, fg_color="transparent")
            f.grid(row=row, column=col, padx=8, pady=3, sticky="w")
            ctk.CTkLabel(f, text=label, font=(MONO, 7), text_color=MUTED).pack(anchor="w")
            lbl = ctk.CTkLabel(f, text="—", font=(MONO, 10, "bold"), text_color=ACCENT3)
            lbl.pack(anchor="w")
            self.hw_labels[key] = lbl

        # ── Buttons ────────────────────────────
        btn_f = ctk.CTkFrame(body, fg_color="transparent")
        btn_f.pack(fill="x", **P)

        self.btn_start   = self._btn(btn_f, "▶ RUN ALL",  ACCENT,  lambda: self._run("all"))
        self.btn_cpu     = self._btn(btn_f, "CPU",        ACCENT,  lambda: self._run("cpu"))
        self.btn_gpu     = self._btn(btn_f, "GPU",        ACCENT3, lambda: self._run("gpu"))
        self.btn_ram     = self._btn(btn_f, "RAM",        ACCENT4, lambda: self._run("ram"))
        self.btn_storage = self._btn(btn_f, "STORAGE",    ACCENT2, lambda: self._run("storage"))
        self.btn_reset   = self._btn(btn_f, "RESET",      MUTED,   self._reset)
        for b in [self.btn_start, self.btn_cpu, self.btn_gpu,
                  self.btn_ram, self.btn_storage, self.btn_reset]:
            b.pack(side="left", padx=(0, 6), pady=8)

        # ── Total score ────────────────────────
        tot_f = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=3,
                              border_color=BORDER, border_width=1)
        tot_f.pack(fill="x", **P)
        inner_t = ctk.CTkFrame(tot_f, fg_color="transparent")
        inner_t.pack(pady=14, padx=20)
        ctk.CTkLabel(inner_t, text="IRONMARK SCORE", font=(MONO, 9), text_color=MUTED).pack()
        self.lbl_total   = ctk.CTkLabel(inner_t, text="—",
                                         font=(SANS, 52, "bold"), text_color=TEXT)
        self.lbl_total.pack()
        self.lbl_grade   = ctk.CTkLabel(inner_t, text="", font=(MONO, 12, "bold"), text_color=MUTED)
        self.lbl_grade.pack()
        self.lbl_verdict = ctk.CTkLabel(inner_t, text="Нажмите Run All для запуска",
                                         font=(MONO, 9), text_color=MUTED)
        self.lbl_verdict.pack()

        # ── Cards 2×2 ──────────────────────────
        cards_f = ctk.CTkFrame(body, fg_color="transparent")
        cards_f.pack(fill="x", padx=18, pady=(8, 0))
        cards_f.grid_columnconfigure((0, 1), weight=1)

        self.cards = {}
        defs = [
            ("cpu",     "CPU",     ACCENT,  "⚙",  "Single/Multi-thread · Matrix · Prime", 0, 0),
            ("gpu",     "GPU",     ACCENT3, "▣",  "Compute · Bandwidth · Fill Rate",       0, 1),
            ("ram",     "MEMORY",  ACCENT4, "▤",  "Bandwidth · Latency · Copy",            1, 0),
            ("storage", "STORAGE", ACCENT2, "▥",  "Seq Read/Write · 4K IOPS",              1, 1),
        ]
        for cid, name, color, icon, desc, row, col in defs:
            self.cards[cid] = self._card(cards_f, cid, name, color, icon, desc, row, col)

        # ── Log ────────────────────────────────
        ctk.CTkLabel(body, text="LOG", font=(MONO, 8), text_color=MUTED).pack(
            anchor="w", padx=20, pady=(10, 0))
        self.log_box = ctk.CTkTextbox(body, height=150, fg_color=SURFACE,
                                       text_color=MUTED, font=(MONO, 9),
                                       border_color=BORDER, border_width=1, corner_radius=3)
        self.log_box.pack(fill="x", padx=18, pady=(2, 14))
        self._log("IRONMARK готов.")
        if HAS_OPENCL:
            self._log("OpenCL обнаружен — GPU будет протестирован напрямую.")
        else:
            self._log("pyopencl не установлен — GPU тест работает через CPU-proxy (tier scoring).")

    def _btn(self, parent, text, color, cmd):
        return ctk.CTkButton(parent, text=text, command=cmd,
                             fg_color="transparent", border_color=color, border_width=1,
                             text_color=color, hover_color="#1a1a22",
                             font=(MONO, 10), corner_radius=2, height=32)

    def _card(self, parent, cid, name, color, icon, desc, row, col):
        f = ctk.CTkFrame(parent, fg_color=SURFACE, border_color=BORDER,
                          border_width=1, corner_radius=3)
        f.grid(row=row, column=col,
               padx=(0, 6) if col == 0 else (0, 0),
               pady=(0, 6), sticky="nsew", ipadx=2)

        top = ctk.CTkFrame(f, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(top, text=f"{icon} {name}", font=(SANS, 12, "bold"),
                     text_color=TEXT).pack(side="left")
        status = ctk.CTkLabel(top, text="IDLE", font=(MONO, 8), text_color=MUTED)
        status.pack(side="right")

        ctk.CTkLabel(f, text=desc, font=(MONO, 8), text_color=MUTED).pack(
            anchor="w", padx=12, pady=(2, 6))

        score_row = ctk.CTkFrame(f, fg_color="transparent")
        score_row.pack(fill="x", padx=12, pady=(0, 2))
        lbl_score = ctk.CTkLabel(score_row, text="0", font=(SANS, 34, "bold"), text_color=color)
        lbl_score.pack(side="left")
        ctk.CTkLabel(score_row, text=" / 10000", font=(MONO, 10), text_color=MUTED).pack(
            side="left", pady=(8, 0))

        pb = ctk.CTkProgressBar(f, progress_color=color, fg_color=BORDER,
                                  height=3, corner_radius=0)
        pb.pack(fill="x", padx=12, pady=(0, 6))
        pb.set(0)

        detail = ctk.CTkLabel(f, text="Не запущен", font=(MONO, 8),
                               text_color=MUTED, wraplength=320, justify="left")
        detail.pack(anchor="w", padx=12, pady=(0, 4))

        sub = ctk.CTkFrame(f, fg_color=BG, corner_radius=0)
        sub.pack(fill="x", padx=12, pady=(2, 10))

        return {"status": status, "score": lbl_score, "pb": pb,
                "detail": detail, "sub": sub, "color": color}

    # ── HW detect ─────────────────────────────────────────────────────────────
    def _detect_hw(self):
        def run():
            info = get_hw_info()
            self.hw = info
            def up():
                self.hw_labels["cpu_name"].configure(text=info["cpu_name"][:42])
                self.hw_labels["cores"].configure(
                    text=f"{info['cpu_cores_physical']}P / {info['cpu_cores_logical']} threads")
                self.hw_labels["gpu_name"].configure(text=info["gpu_name"][:36])
                self.hw_labels["gpu_vram"].configure(
                    text=f"{info['gpu_vram']} GB" if info["gpu_vram"] else "—")
                self.hw_labels["ram"].configure(text=f"{info['ram_total_gb']} GB")
                self.hw_labels["ram_type"].configure(
                    text=f"{info['ram_type']} {info['ram_speed']} MT/s" if info["ram_speed"] else info["ram_type"])
                self.hw_labels["storage"].configure(
                    text=f"{int(info['storage_total_gb'])} GB  {info['storage_type']}")
                self.hw_labels["os"].configure(text=f"{info['os']} {info['arch']}")
            self.after(0, up)
        threading.Thread(target=run, daemon=True).start()

    # ── Log ───────────────────────────────────────────────────────────────────
    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        def do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{ts}] {msg}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, do)

    # ── Card helpers ──────────────────────────────────────────────────────────
    def _card_status(self, cid, s):
        col = {"idle": MUTED, "running": ACCENT4, "done": ACCENT}.get(s, MUTED)
        self.after(0, lambda: self.cards[cid]["status"].configure(
            text=s.upper(), text_color=col))

    def _animate_score(self, cid, target):
        card = self.cards[cid]
        cur  = [0]
        step = max(1, target // 50)
        def tick():
            cur[0] = min(cur[0] + step, target)
            card["score"].configure(text=str(cur[0]))
            card["pb"].set(cur[0] / 10000)
            if cur[0] < target:
                self.after(18, tick)
        self.after(0, tick)

    def _set_sub(self, cid, details):
        card = self.cards[cid]
        def do():
            for w in card["sub"].winfo_children():
                w.destroy()
            for k, v in details.items():
                row = ctk.CTkFrame(card["sub"], fg_color="transparent")
                row.pack(fill="x", padx=6, pady=1)
                ctk.CTkLabel(row, text=k, font=(MONO, 8), text_color=MUTED).pack(side="left")
                val_col  = card["color"] if isinstance(v, int) else TEXT
                val_text = f"{v} pts" if isinstance(v, int) else str(v)
                ctk.CTkLabel(row, text=val_text, font=(MONO, 8, "bold"),
                             text_color=val_col).pack(side="right")
        self.after(0, do)

    def _set_total(self, score):
        grade, color, verdict = get_grade(score)
        def do():
            cur  = [0]
            step = max(1, score // 60)
            def tick():
                cur[0] = min(cur[0] + step, score)
                self.lbl_total.configure(text=f"{cur[0]:,}".replace(",", " "), text_color=color)
                if cur[0] < score:
                    self.after(18, tick)
            tick()
            self.lbl_grade.configure(text=f"[ {grade} ]  {verdict}", text_color=color)
            self.lbl_verdict.configure(
                text=(f"CPU {self.scores['cpu']}  ·  GPU {self.scores['gpu']}  "
                      f"·  RAM {self.scores['ram']}  ·  SSD {self.scores['storage']}"))
        self.after(0, do)

    # ── Run ───────────────────────────────────────────────────────────────────
    def _set_buttons(self, enabled):
        s = "normal" if enabled else "disabled"
        for b in [self.btn_start, self.btn_cpu, self.btn_gpu, self.btn_ram, self.btn_storage]:
            b.configure(state=s)

    def _run(self, mode):
        if self.running:
            return
        self.running = True
        self._set_buttons(False)
        threading.Thread(target=self._run_thread, args=(mode,), daemon=True).start()

    def _run_thread(self, mode):
        self._log(f"═══ START: {mode.upper()} ═══")

        def do(cid, fn):
            self._card_status(cid, "running")
            def prog(pct):
                self.after(0, lambda: self.cards[cid]["pb"].set(pct / 100))
            score, details = fn(prog, self._log)
            self.scores[cid] = score
            self._animate_score(cid, score)
            self._set_sub(cid, details)
            self._card_status(cid, "done")
            self._log(f"[{cid.upper()}] ✓ {score}/10000")
            time.sleep(0.2)

        if mode == "all":
            do("cpu", bench_cpu)
            do("gpu", bench_gpu)
            do("ram", bench_ram)
            do("storage", bench_storage)
            total = int(
                self.scores["cpu"]     * 0.35 +
                self.scores["gpu"]     * 0.30 +
                self.scores["ram"]     * 0.20 +
                self.scores["storage"] * 0.15
            )
            self._set_total(total)
            self._log(f"═══ IRONMARK TOTAL: {total}/10000 ═══")
        elif mode == "cpu":     do("cpu",     bench_cpu)
        elif mode == "gpu":     do("gpu",     bench_gpu)
        elif mode == "ram":     do("ram",     bench_ram)
        elif mode == "storage": do("storage", bench_storage)

        self.running = False
        self.after(0, lambda: self._set_buttons(True))

    # ── Reset ─────────────────────────────────────────────────────────────────
    def _reset(self):
        if self.running:
            return
        self.scores = {"cpu": 0, "gpu": 0, "ram": 0, "storage": 0}
        for cid, card in self.cards.items():
            card["score"].configure(text="0")
            card["pb"].set(0)
            card["status"].configure(text="IDLE", text_color=MUTED)
            card["detail"].configure(text="Не запущен")
            for w in card["sub"].winfo_children():
                w.destroy()
        self.lbl_total.configure(text="—", text_color=TEXT)
        self.lbl_grade.configure(text="")
        self.lbl_verdict.configure(text="Нажмите Run All для запуска", text_color=MUTED)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log("Сброшено.")


# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = IronmarkApp()
    app.mainloop()
