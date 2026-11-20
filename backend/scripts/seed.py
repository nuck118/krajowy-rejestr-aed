import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.v1.stats import get_stats  # noqa: E402
from app.db.session import async_session_factory, init_db_schema  # noqa: E402
from app.services.ingestion_runner import execute_ingestion_run  # noqa: E402


async def main(with_overpass: bool = False) -> None:
    await init_db_schema()

    async with async_session_factory() as session:
        pl_run = await execute_ingestion_run(session, source="pl_geojson")
        print(
            f"[pl_geojson] fetched={pl_run.records_fetched} valid={pl_run.records_valid} "
            f"rejected={pl_run.records_rejected} inserted={pl_run.records_inserted} "
            f"merged={pl_run.duplicates_merged} time={pl_run.duration_ms}ms"
        )

        if with_overpass:
            osm_run = await execute_ingestion_run(session, source="osm_overpass")
            print(
                f"[osm_overpass] fetched={osm_run.records_fetched} valid={osm_run.records_valid} "
                f"rejected={osm_run.records_rejected} inserted={osm_run.records_inserted} "
                f"merged={osm_run.duplicates_merged} time={osm_run.duration_ms}ms"
            )

        stats = await get_stats(session)
        print(
            f"[stats] total_unified_aeds={stats.total_unified_aeds} "
            f"duplicates_merged={stats.duplicates_merged} "
            f"active_sources={stats.active_sources} "
            f"national_completeness_avg={stats.national_completeness_avg}%"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Krajowy Rejestr AED from real Polish datasets")
    parser.add_argument(
        "--with-overpass",
        action="store_true",
        help="Also query live OpenStreetMap Overpass API for Bydgoszcz",
    )
    args = parser.parse_args()
    asyncio.run(main(with_overpass=args.with_overpass))
