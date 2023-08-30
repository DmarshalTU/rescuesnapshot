import os
import sys
import logging
import time
import concurrent.futures
from kubernetes import client, config
from prometheus_client import start_http_server, Counter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

# Define Prometheus metrics
DELETED_SNAPSHOTS = Counter('deleted_snapshots_total', 'Total number of deleted snapshots')

class SnapshotCleaner:

    def __init__(self, delete_after, batch_size=50, max_threads=10):
        self.delete_after = delete_after
        self.batch_size = batch_size
        self.max_threads = max_threads
        # Using in-cluster configuration
        config.load_incluster_config()
        self.api_instance = client.CustomObjectsApi()

    def fetch_snapshots(self):
        logging.info("Fetching snapshots...")
        snapshots = self.api_instance.list_namespaced_custom_object(
            group="rke.cattle.io",
            version="v1",
            namespace="fleet-default",
            plural="etcdsnapshots",
        )
        return [
            item["metadata"]["name"]
            for item in snapshots.get("items", [])
            if item.get("status", {}).get("missing")
        ]

    def delete_snapshot(self, snapshot_name):
        logging.info(f"Deleting snapshot: {snapshot_name}")
        try:
            self.api_instance.delete_namespaced_custom_object(
                group="rke.cattle.io",
                version="v1",
                namespace="fleet-default",
                plural="etcdsnapshots",
                name=snapshot_name,
                body=client.V1DeleteOptions(),
            )
            DELETED_SNAPSHOTS.inc()
        except Exception as e:
            logging.error(f"Error deleting snapshot {snapshot_name}: {e}")

    def main(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            while True:
                missing_snapshots = self.fetch_snapshots()
                logging.info(f"Found {len(missing_snapshots)} missing snapshots.")

                futures = [executor.submit(self.delete_snapshot, snapshot) for snapshot in missing_snapshots]
                concurrent.futures.wait(futures)

                # Sleep for a shorter time if there were missing snapshots, else sleep longer
                sleep_time = 1 if missing_snapshots else 1
                time.sleep(sleep_time)

if __name__ == "__main__":
    # Start Prometheus metrics server
    start_http_server(8000)
    
    # Getting DELETE_AFTER value from environment variable
    delete_after = int(os.getenv("DELETE_AFTER", 1))
    cleaner = SnapshotCleaner(delete_after)
    cleaner.main()
