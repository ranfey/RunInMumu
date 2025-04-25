import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np
from prettytable import PrettyTable

JITTER_RADIUS_M = 2.0  # 定位抖动半径（米）（模拟定位失真）
BASE_SPEED_MPS = 4.5  # 平均速度（米/秒）
SPEED_JITTER_RATIO = 0.20  # 速度波动 ±20%（模拟步频）
TICK_INTERVAL_SEC = 0.40  # 广播间隔（秒）
DIST_LIMIT_M = 16000  # 总距离阈值（米）“”是的，我常年霸榜榜一“”

TAP_DELAY_SEC = 1.0  # 每轮模拟点击间隔
WINDOW_DELAY_SEC = 15.0  # 等待应用打开的时间，性能差请调大

WALK_PATH: List[Tuple[float, float]] = [
    (106.573302, 29.508911),
    (106.574330, 29.509245),
    (106.575602, 29.508467),
    (106.574259, 29.508012),
    (106.571092, 29.508342),
    (106.573513, 29.508640),
]  # 从百度地图之类的工具取经纬度加入列表即可，默认为兰花胡的定位，会列表循环

CLR_A = "\x1b[01;38;5;117m"  # 千世默认主色调：亮蓝青，活泼元气 ✧
CLR_P = "\x1b[01;38;5;153m"  # 淡青紫蓝：轻盈梦幻 ✿
CLR_C = "\x1b[01;38;5;123m"  # 软蓝绿调：亲切温柔 (｡•̀ᴗ-)✧
HEART = "\x1b[01;38;5;195m"  # 高光粉蓝：强调效果用，bling bling✨
CLR_RST = "\x1b[0m"  # 重置色彩～


def find_emu_dir() -> Path:
    cfg = Path("config.json")
    if cfg.exists():
        try:
            emu_dir = Path(json.loads(cfg.read_text(encoding="utf-8"))["emu_dir"])
            if emu_dir.joinpath("MuMuManager.exe").is_file():
                return emu_dir
        except Exception:
            pass
    search_roots = [
        Path(f"{d}:\\Program Files\\NetEase") for d in "CDEFGHIJKLMNOPQRSTUVWXYZ"
    ] + [
        Path(f"{d}:\\Program Files (x86)\\NetEase") for d in "CDEFGHIJKLMNOPQRSTUVWXYZ"
    ]
    for base in search_roots:
        for p in base.rglob("MuMuManager.exe"):
            emu_dir = p.parent
            cfg.write_text(json.dumps({"emu_dir": str(emu_dir)}), encoding="utf-8")
            return emu_dir
    sys.exit(f"{CLR_A}× 千世找不到MuMu…老师你真的装了吗？…{CLR_RST}")


def meter_to_deg(lat: float, dx: float, dy: float) -> Tuple[float, float]:
    d_lat = dy / 111_320
    d_lon = dx / (111_320 * math.cos(math.radians(lat)))
    return d_lat, d_lon


def set_location(mgr_path: Path, lon: float, lat: float) -> None:
    dx, dy = (random.uniform(-JITTER_RADIUS_M, JITTER_RADIUS_M) for _ in range(2))
    d_lat, d_lon = meter_to_deg(lat, dx, dy)
    subprocess.run(
        [
            str(mgr_path),
            "control",
            "-v",
            "0",
            "tool",
            "location",
            "-lon",
            f"{lon + d_lon:.6f}",
            "-lat",
            f"{lat + d_lat:.6f}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def click_icon(
    adb: Path,
    icon_png: str,
    threshold: float = 0.75,
    offset: Tuple[int, int] = (0, 0),
    long_press: bool = False,
) -> bool:
    screen_png = Path("screen.png")
    with screen_png.open("wb") as fp:
        subprocess.run([str(adb), "exec-out", "screencap", "-p"], stdout=fp)
    screen = cv2.imread(str(screen_png))
    icon = cv2.imread(icon_png)
    if screen is None or icon is None:
        print(f"{CLR_A}× 图像加载失败了啦！{CLR_RST}")
        return False
    res = cv2.matchTemplate(screen, icon, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < threshold:
        # print(f"{HEART}… 没找到 {icon_png} ～（置信度只有 {score:.3f} 哦）{CLR_RST}")
        return False
    x, y = (
        loc[0] + icon.shape[1] // 2 + offset[0],
        loc[1] + icon.shape[0] // 2 + offset[1],
    )
    cmd = (
        ["swipe", str(x), str(y), str(x), str(y), "2000"]
        if long_press
        else ["tap", str(x), str(y)]
    )
    subprocess.run([str(adb), "shell", "input"] + cmd)
    print(
        f"{HEART}🦀 应该就是这个吧，我要点了哦~ {icon_png} @ ({x},{y}) ～ 置信度 {score:.3f}{CLR_RST}"
    )
    return True


def geo_dist_m(lat1, lon1, lat2, lon2) -> float:
    return math.hypot(lat2 - lat1, lon2 - lon1) * 111_320


def launch_emulator(emu_dir: Path) -> Tuple[Path, Path]:
    mgr = emu_dir / "MuMuManager.exe"
    player = emu_dir / "MuMuPlayer.exe"
    adb = emu_dir / "adb.exe"
    subprocess.Popen(player)
    print(f"{CLR_P}🦀 MuMu 正在启动了啦~{CLR_RST}")
    pkgs = {"com.tencent.mm", "com.tencent.wework"}
    while True:
        try:
            out = subprocess.check_output(
                [str(mgr), "control", "-v", "0", "app", "info", "-i"], encoding="utf-8"
            )
            if pkgs.issubset(json.loads(out)):
                break
        except Exception:
            pass
        time.sleep(2)
    for p in pkgs:
        subprocess.Popen([str(mgr), "control", "-v", "0", "app", "launch", "-pkg", p])
        time.sleep(WINDOW_DELAY_SEC)
    adb_info = json.loads(
        subprocess.check_output([str(mgr), "info", "-v", "0"], encoding="utf-8")
    )
    adb_addr = f"{adb_info['adb_host_ip']}:{adb_info['adb_port']}"
    subprocess.run([str(adb), "connect", adb_addr], stdout=subprocess.DEVNULL)
    print(f"{CLR_C}🦀 连接上啦 ADB：{adb_addr} ～千世准备好了哦～{CLR_RST}")
    subprocess.run(
        [
            str(adb),
            "shell",
            "monkey",
            "-p",
            "com.tencent.wework",
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ]
    )
    return mgr, adb


def pre_run_ui(adb: Path, mgr_path: Path) -> None:
    while not click_icon(adb, "img/lepao.png"):
        click_icon(adb, "img/gongzuotai.png")
        click_icon(adb, "img/tiyv.png")
        time.sleep(TAP_DELAY_SEC)
    lon, lat = WALK_PATH[0]
    set_location(mgr_path, lon, lat)
    while not click_icon(adb, "img/zhenquelepao.png"):
        click_icon(adb, "img/lepao.png")
        click_icon(adb, "img/kaishilepao.png")
        click_icon(adb, "img/zhiyoupao.png")
        click_icon(adb, "img/kaishil.png", offset=(320, -1404))
        click_icon(adb, "img/chongxin.png")
        time.sleep(TAP_DELAY_SEC)
    time.sleep(4)


def simulate_walk(mgr_path: Path, route: List[Tuple[float, float]]) -> None:
    idx, seg_dist, total_dist = 0, 0.0, 0.0
    t_start = t_prev = time.perf_counter()
    next_tick = t_prev + TICK_INTERVAL_SEC
    frame = 0
    while True:
        now = time.perf_counter()
        if now < next_tick:
            time.sleep(next_tick - now)
            now = next_tick
        next_tick += TICK_INTERVAL_SEC
        dt = now - t_prev
        t_prev = now
        lon1, lat1 = route[idx]
        lon2, lat2 = route[(idx + 1) % len(route)]
        seg_len = geo_dist_m(lat1, lon1, lat2, lon2)
        speed = BASE_SPEED_MPS * random.uniform(
            1 - SPEED_JITTER_RATIO, 1 + SPEED_JITTER_RATIO
        )
        move = speed * dt
        seg_dist += move
        total_dist += move
        while seg_dist >= seg_len:
            seg_dist -= seg_len
            idx = (idx + 1) % len(route)
            lon1, lat1 = route[idx]
            lon2, lat2 = route[(idx + 1) % len(route)]
            seg_len = geo_dist_m(lat1, lon1, lat2, lon2)
        ratio = seg_dist / seg_len
        lon = lon1 + (lon2 - lon1) * ratio
        lat = lat1 + (lat2 - lat1) * ratio
        set_location(mgr_path, lon, lat)
        frame += 1
        elapsed = now - t_start
        tbl = PrettyTable(["时间", "即时速度", "总路程", "均速", "步频"])
        tbl.add_row(
            [
                f"{CLR_P}{elapsed:7.2f}{CLR_RST}s",
                f"{CLR_P}{speed:7.2f}{CLR_RST}m/s",
                f"{CLR_P}{total_dist:8.2f}{CLR_RST}m",
                f"{CLR_P}{total_dist/elapsed:7.2f}{CLR_RST}m/s",
                f"{CLR_P}{frame/elapsed:7.2f}{CLR_RST}Hz",
            ]
        )
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{HEART}🦀 千世很快就跑完啦~")
        print(tbl)
        if total_dist >= DIST_LIMIT_M:
            print(f"{CLR_A}🦀 啊咧？已经跑够啦～ 🦀{CLR_RST}")
            break


def post_run_ui(adb: Path) -> None:
    seq = [
        ("img/jieshu.png", {"long_press": True}),
        ("img/jieshu2.png", {}),
        ("img/jieshu3.png", {}),
        ("img/diandian.png", {}),
        ("img/chongxin.png", {}),
    ]
    for icon, kw in seq:
        if click_icon(adb, icon, **kw):
            time.sleep(TAP_DELAY_SEC)


if __name__ == "__main__":
    emu_dir = find_emu_dir()
    mgr_path, adb_path = launch_emulator(emu_dir)
    pre_run_ui(adb_path, mgr_path)
    simulate_walk(mgr_path, WALK_PATH)
    post_run_ui(adb_path)
