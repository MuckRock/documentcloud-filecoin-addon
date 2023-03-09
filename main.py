"""
This is a Filecoin add-on for DocumentCloud.
"""

import os
import sys
import time
from datetime import datetime

from documentcloud.addon import AddOn, SoftTimeOutAddOn
from documentcloud.toolbox import requests_retry_session
from requests.exceptions import RequestException


class Filecoin(SoftTimeOutAddOn):
    def fail(self, i, document):
        print(f"{datetime.now()} - Uploading {i} {document.slug} failed")
        self.set_message("Uploading failed")
        # sleep until soft time out limit
        time.sleep(max(self._start + self.soft_time_limit - time.time(), 0))
        self.rerun_addon(include_current=True)
        sys.exit()

    def main(self):
        """Push the file to filecoin and store the IPFS CID back to DocumentCloud"""

        estuary_token = os.environ["TOKEN"]

        total = self.get_document_count()
        print(f"{datetime.now()} - Total documents: {total}")
        for i, document in enumerate(self.get_documents()):
            print(
                f"{datetime.now()} - Uploading {i} {document.slug} size "
                f"{len(document.pdf)}"
            )
            try:
                response = requests_retry_session(retries=8).post(
                    "https://api.estuary.tech/content/add",
                    headers={"Authorization": f"Bearer {estuary_token}"},
                    files={
                        "data": (
                            f"{document.slug}.pdf",
                            document.pdf,
                            "application/pdf",
                        )
                    },
                    timeout=30,
                )
            except RequestException as exc:
                print(exc)
                self.fail(i, document)
            print(f"{datetime.now()} - Uploading {i} {document.slug} complete")
            if response.status_code >= 400:
                print(response.text)
                response.raise_for_status()
            elif response.status_code >= 500:
                print(response.text)
                self.fail(i, document)
            else:
                print(f"{datetime.now()} - Set metadata for {i} {document.slug}")
                data = response.json()
                document.data["cid"] = [data["cid"]]
                document.data["estuaryId"] = [str(data["estuaryId"])]
                ipfs_url = f"https://dweb.link/ipfs/{data['cid']}"
                document.data["ipfsUrl"] = [ipfs_url]
                document.save()
                try:
                    self.set_message(f"Upload complete - {ipfs_url}")
                    self.set_progress(int(100 * (i + 1) / total))
                except RequestException:
                    print("Error updating message/progress")
                print(f"{datetime.now()} - Set metadata for {i} {document.slug} done")


if __name__ == "__main__":
    Filecoin().main()
