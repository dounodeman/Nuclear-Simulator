"""Draw the app icon (a core grid in Cherenkov blue) and, on macOS, pack it as icon.icns.

    python packaging/macos/make_icon.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent


def draw(path: Path, px: int = 1024) -> None:
    fig = plt.figure(figsize=(1, 1), dpi=px)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_alpha(0)
    # macOS icon grid: artwork inset about 10% with a rounded square.
    ax.add_patch(FancyBboxPatch((0.1, 0.1), 0.8, 0.8, boxstyle="round,pad=0,rounding_size=0.18",
                                fc="#0b1620", ec="none"))
    for r, a in ((0.33, 0.10), (0.26, 0.16), (0.2, 0.25)):
        ax.add_patch(Circle((0.5, 0.53), r, fc="#4fc3f7", alpha=a, ec="none"))
    # 4 x 4 core grid with three control-blade slots
    s, g = 0.075, 0.012
    x0 = 0.5 - 2 * s - 1.5 * g
    y0 = 0.53 - 2 * s - 1.5 * g
    for i in range(4):
        for j in range(4):
            control = (i, j) in ((1, 2), (2, 1), (2, 2))
            ax.add_patch(Rectangle((x0 + i * (s + g), y0 + j * (s + g)), s, s,
                                   fc="#c084fc" if control else "#d7f2ff", ec="none",
                                   alpha=0.95))
    ax.text(0.5, 0.19, "PUR-1", ha="center", va="center", color="#e6f6ff",
            fontsize=8, fontweight="bold", family="DejaVu Sans Mono")
    fig.savefig(path, dpi=px, transparent=True)
    plt.close(fig)


def main() -> int:
    png = HERE / "icon.png"
    draw(png)
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        print(f"wrote {png} (icon.icns needs macOS iconutil)")
        return 0
    iconset = HERE / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            subprocess.run(["sips", "-z", str(size * scale), str(size * scale), str(png),
                            "--out", str(iconset / name)], check=True, capture_output=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "icon.icns")], check=True)
    shutil.rmtree(iconset)
    print(f"wrote {HERE / 'icon.icns'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
