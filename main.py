"""
This is a Filecoin add-on for DocumentCloud.
"""

import os

import requests
from documentcloud.addon import AddOn


class Filecoin(AddOn):
    def main(self):
        """Push the file to filecoin and store the IPFS CID back to DocumentCloud"""

        estuary_token = os.environ["ESTUARY_TOKEN"]

        for doc_id in self.documents:
            document = self.client.documents.get(doc_id)
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
                document.data["ipfsUrl"] = [f"https://dweb.link/ipfs/{data['cid']}"]
                document.save()


if __name__ == "__main__":
    Filecoin().main()
