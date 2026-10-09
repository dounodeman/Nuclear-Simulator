# PyInstaller spec for the PUR-1 Simulator Mac app.
#   pip install ".[mac]"
#   pyinstaller packaging/macos/pur1.spec --noconfirm
# produces "dist/PUR-1 Simulator.app".
from pathlib import Path

from reactorsim import __version__, _build

ROOT = Path(SPECPATH).resolve().parents[1]
APP = "PUR-1 Simulator"
ICON = ROOT / "packaging" / "macos" / "icon.icns"

a = Analysis(
    [str(ROOT / "packaging" / "macos" / "launch.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "reactorsim" / "app" / "static"), "reactorsim/app/static"),
        (str(ROOT / "models" / "export"), "models/export"),
    ],
    hiddenimports=["webview.platforms.cocoa"],
    excludes=["matplotlib", "tkinter", "pytest", "IPython", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP,
    console=False,
    target_arch=None,  # the runner's architecture (Apple silicon on macos-14)
    codesign_identity=None,  # ad-hoc signature
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP)
app = BUNDLE(
    coll,
    name=f"{APP}.app",
    icon=str(ICON) if ICON.exists() else None,
    bundle_identifier="io.github.dounodeman.pur1-simulator",
    version=f"{__version__}.{_build.BUILD}",
    info_plist={
        "CFBundleDisplayName": APP,
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": str(_build.BUILD),
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        "LSApplicationCategoryType": "public.app-category.education",
    },
)
