"""
This is a Filecoin add-on for DocumentCloud.
"""

import os
from datetime import datetime

from documentcloud.addon import AddOn
from documentcloud.toolbox import requests_retry_session
from requests.exceptions import RequestException


class Filecoin(AddOn):
    def main(self):
        """Push the file to filecoin and store the IPFS CID back to DocumentCloud"""

        estuary_token = os.environ["TOKEN"]

        total = self.get_document_count()
        print(f"{datetime.now()} - Total documents: {total}")
        for i, document in enumerate(self.get_documents()):
            print(f"{datetime.now()} - Uploading {i} {document.slug} size {len(document.pdf)}")
            response = requests_retry_session(retries=8).post(
                "https://upload.estuary.tech/content/add",
                headers={"Authorization": f"Bearer {estuary_token}"},
                files={
                    "data": (f"{document.slug}.pdf", document.pdf, "application/pdf")
                },
            )
            print(f"{datetime.now()} - Uploading {i} {document.slug} complete")
            if response.status_code != 200:
                print(f"{datetime.now()} - Uploading {i} {document.slug} failed")
                self.set_message("Uploading failed")
                response.raise_for_status()
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
                    self.set_progress(int(100 * (i + 1)/ total))
                except RequestException:
                    print("Error updating message/progress")
                print(f"{datetime.now()} - Set metadata for {i} {document.slug} done")


if __name__ == "__main__":
    Filecoin().main()
