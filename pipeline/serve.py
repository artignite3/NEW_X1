"""Server entrypoint: restore and verify the published release before opening the API port."""
import os
from pathlib import Path
import threading

from dotenv import load_dotenv


def main():
    import uvicorn
    from pipeline.object_store import configured_store
    from pipeline.releases import restore_release
    from pipeline.serving import SNAPSHOT_LOCK, apply_release, refresh_once

    load_dotenv()
    store = configured_store()
    cache = Path(os.getenv("RELEASE_CACHE_DIR", "outputs/releases"))
    root, manifest, recovery = restore_release(store, cache)
    with SNAPSHOT_LOCK:
        apply_release(root, manifest, recovery)

    interval = max(60, int(os.getenv("RELEASE_POLL_SECONDS", "300")))
    stopped = threading.Event()

    def refresh():
        while not stopped.wait(interval):
            refresh_once(store, cache)

    threading.Thread(target=refresh, daemon=True, name="release-refresh").start()
    try:
        uvicorn.run("model.model_fastapi:app", host=os.getenv("HOST", "0.0.0.0"),
                    port=int(os.getenv("PORT", "8000")), proxy_headers=True,
                    forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "*"))
    finally:
        stopped.set()


if __name__ == "__main__":
    main()
