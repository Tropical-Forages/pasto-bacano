"""Checks the Google Earth Engine setup used by Pasto Bacano.

Reads the GEE_* variables from an env file (default: ./.env), initializes
Earth Engine exactly as the app does (domain.services.geospatial.gee) and
reports which project and identity are in use, whether the project is
registered for Earth Engine, and which of the app's assets can be read.

Usage:
    uv run python scripts/check_gee.py [path/to/env/file]

Only reads data; it creates or changes nothing.
"""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = {
    "Time2Graze monthly biomass": "projects/wri-lcl-time2graze/assets/ugpp_prod_10m_v1",
    "GPW grassland classes v1": "projects/global-pasture-watch/assets/ggc-30m/v1/grassland_c",
    "GPW grassland classes v1-1": "projects/global-pasture-watch/assets/ggc-30m/v1-1/grassland_c",
    "GPW annual uGPP v1-1": "projects/global-pasture-watch/assets/ggpp-30m/v1-1/ugpp_m",
}


def main() -> int:
    env_file = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".env"
    if not env_file.is_file():
        print(f"Env file not found: {env_file}")
        return 1
    values = dotenv_values(env_file)
    for name in ("GEE_PROJECT", "GEE_SERVICE_ACCOUNT", "GEE_KEY_FILE"):
        os.environ[name] = values.get(name) or ""

    project = os.environ["GEE_PROJECT"]
    account = os.environ["GEE_SERVICE_ACCOUNT"]
    key_file = os.environ["GEE_KEY_FILE"]

    print(f"Env file:        {env_file}")
    print(f"GEE_PROJECT:     {project or '(not set)'}")
    if account and key_file:
        print(f"Identity:        service account {account}")
        print(f"Key file:        {key_file} ({'found' if Path(key_file).is_file() else 'NOT FOUND'})")
    else:
        print("Identity:        Application Default Credentials (GEE_SERVICE_ACCOUNT or GEE_KEY_FILE empty)")

    import contextlib
    import io

    import ee

    # Importing the domain package loads the prompts, which logs a line per key.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from domain.services.geospatial.gee import EarthEngineUnavailable, initialize_ee

    try:
        initialize_ee()
    except EarthEngineUnavailable as error:
        print(f"\nInitialization FAILED: {error}")
        return 1

    print(f"\nearthengine-api: {ee.__version__}")
    print(f"Computation:     {'OK' if ee.Number(1).add(1).getInfo() == 2 else 'unexpected result'}")

    try:
        project_config = ee.data.getProjectConfig()
        print(f"Project config:  {project_config.get('name', project)} (registered for Earth Engine)")
    except Exception as error:
        print(f"Project config:  not readable ({error.__class__.__name__}: {error})")

    print("\nAssets:")
    failures = 0
    for label, asset_id in ASSETS.items():
        try:
            asset = ee.data.getAsset(asset_id)
            print(f"  OK      {label}: {asset.get('type', '?')}")
        except Exception as error:
            failures += 1
            print(f"  FAILED  {label}: {error}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
