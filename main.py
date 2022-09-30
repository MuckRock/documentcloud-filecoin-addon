"""
This is a Filecoin add-on for DocumentCloud.
"""

import os

import requests
from documentcloud.addon import AddOn


class Filecoin(AddOn):
    def main(self):
        """Push the file to filecoin and store the IPFS CID back to DocumentCloud"""

        estuary_token = os.environ["TOKEN"]

        for document in self.get_documents():
            response = requests.post(
                "https://shuttle-4.estuary.tech/content/add",
                headers={"Authorization": f"Bearer {estuary_token}"},
                files={
                    "data": (f"{document.slug}.pdf", document.pdf, "application/pdf")
                },
            )
            if response.status_code != 200:
                self.set_message("Uploading failed")
                return
            else:
                data = response.json()
                document.data["cid"] = [data["cid"]]
                document.data["estuaryId"] = [str(data["estuaryId"])]
                ipfs_url = f"https://dweb.link/ipfs/{data['cid']}"
                document.data["ipfsUrl"] = [ipfs_url]
                document.save()
                self.set_message(f"Upload complete - {ipfs_url}")


if __name__ == "__main__":
    Filecoin().main()
