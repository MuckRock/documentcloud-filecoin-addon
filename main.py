"""
This is a Filecoin add-on for DocumentCloud, using filecoin-pin
"""
import os
import re
import subprocess
import sys
import time
from datetime import datetime

import requests

from documentcloud.addon import SoftTimeOutAddOn
from documentcloud.exceptions import APIError

DATA_SET_ID = "1595"
IPNI_LOOKUP = "https://cid.contact/cid/"

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ROOT_CID_RE = re.compile(r"Root CID:\s*(\S+)")


class FilecoinPin(SoftTimeOutAddOn):
    """Add-On to upload files to Filecoin via filecoin-pin"""

    def main(self):
        """Uses the filecoin-pin CLI to upload documents"""
        self.client.session.headers.update({"User-Agent": "Push to IPFS Add-On"})

        # Pass the key to filecoin-pin via token
        env = os.environ.copy()
        env["PRIVATE_KEY"] = os.environ["TOKEN"].strip()

        for i, document in enumerate(self.get_documents()):
            truncated_title = document.title[:220]
            existing_cid = document.data.get("cid")

            if existing_cid and not document.data.get("ipfsUrl"):
                # Pinned on a previous run that failed before IPNI confirmed it,
                # so skip re-pinning and just finish the indexing check to
                # find its IPFSUrl
                cid = existing_cid[0]
                indexed = False
                print(f"{datetime.now()} - {document.slug} already pinned as {cid}")
            else:
                self.set_message(f"Uploading {truncated_title}...")
                print(
                    f"{datetime.now()} - Uploading {i} {document.slug} size "
                    f"{len(document.pdf)}"
                )
                filename = f"{document.slug}.pdf"
                with open(filename, "wb") as pdf:
                    pdf.write(document.pdf)

                try:
                    cid, indexed = self.pin_file(filename, env)
                finally:
                    os.remove(filename)

                # The CID is final as soon as add succeeds, so tag it.
                self.tag_document(document, "cid", [cid])

            if indexed:
                print(f"{datetime.now()} - filecoin-pin confirmed {cid} is indexed")
            else:
                # The CLI didn't see IPNI records yet
                # or this is a document from a previous run that failed but 
                # cid was correctly set, so poll cid.contact ourselves
                indexed = self.is_indexed(cid)

            # If after polling again it still isn't indexed, we should raise because this may point
            # to deeper network issues.
            if not indexed:
                self.set_message(
                    f"Error: {truncated_title} was pinned but is not yet "
                    "retrievable over IPFS. Try again later."
                )
                raise ValueError(f"{cid} not found in IPNI after polling")
            # Both documents that were indexed immediately
            # and which the poller later found to be indexed get tagged with their ipfsUrl
            self.tag_document(
                document, "ipfsUrl", [f"https://{cid}.ipfs.dweb.link"]
            )

    def pin_file(self, filename, env):
        """Runs filecoin-pin add and returns the root CID and whether IPNI has it"""
        result = subprocess.run(
            ["filecoin-pin", "add", filename, "--data-set-id", DATA_SET_ID],
            capture_output=True,
            env=env,
            check=False,
        )
        stdout = ANSI_ESCAPE.sub("", result.stdout.decode("utf8", errors="replace"))
        stderr = ANSI_ESCAPE.sub("", result.stderr.decode("utf8", errors="replace"))

        if result.returncode != 0:
            print(f"filecoin-pin exited with code {result.returncode}")
            print(f"stdout:\n{stdout}")
            print(f"stderr:\n{stderr}")
            self.set_message(f"Error: {stderr[:220] or stdout[-220:]}")
            raise ValueError(f"filecoin-pin add failed (exit {result.returncode})")

        match = ROOT_CID_RE.search(stdout)
        if not match:
            self.set_message("Error: could not find Root CID in filecoin-pin output")
            raise ValueError(f"No Root CID in output:\n{stdout}")
        indexed = "IPNI provider records found" in stdout
        return match.group(1), indexed

    def is_indexed(self, cid, max_retries=6, retry_delay=10, max_delay=120):
        """Check the IPNI index for the CID, retrying with backoff while it propagates."""
        retries = 0
        while retries < max_retries:
            try:
                print(f"Checking IPNI for {cid}...")
                resp = requests.get(
                    f"{IPNI_LOOKUP}{cid}",
                    headers={"User-Agent": "Push to IPFS Add-On"},
                    timeout=30,
                )
                if resp.status_code == 200:
                    print(f"{cid} is indexed")
                    return True
                print(f"{cid} not indexed yet (status {resp.status_code}). Retrying...")
            except requests.RequestException as exc:
                print(f"Error checking IPNI for {cid}. {exc}. Retrying...")
            retries += 1
            if retries < max_retries:
                time.sleep(min(retry_delay * 2 ** (retries - 1), max_delay))
        else:
            print(f"{cid} not indexed after {max_retries} attempts.")
            return False

    def tag_document(self, document, key, values, max_retries=5, retry_delay=60):
        """Tag the document with a data key, replacing existing values, retrying on API errors."""
        retries = 0
        while retries < max_retries:
            try:
                print(f"Tagging document {document.id} with {key}...")
                existing = document.data.get(key, [])
                self.client.patch(
                    f"documents/{document.id}/data/{key}/",
                    json={"values": values, "remove": existing},
                )
                self.client.patch(
                    f"documents/{document.id}/data/{key}/",
                    json={"values": values},
                )
                document.data[key] = values  # keep local copy in sync
                print(f"Finished tagging document with {key}")
                break
            except APIError as exc:
                print(f"Error tagging document with {key}. {exc}. Retrying...")
                retries += 1
                time.sleep(retry_delay)
        else:
            print(f"Failed to tag document with {key} after {max_retries} attempts.")
            self.set_message(
                f"Failed to set the {key} tag for this document. "
                "Email info@documentcloud.org to debug."
            )
            sys.exit(1)


if __name__ == "__main__":
    FilecoinPin().main()