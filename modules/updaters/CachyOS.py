import re
from functools import cache
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from modules.exceptions import VersionNotFoundError
from modules.updaters.GenericUpdater import GenericUpdater
from modules.utils import sha256_hash_check

DOMAIN = "https://cdn.cachyos.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/ISO"
FILE_NAME = "cachyos-[[EDITION]]-linux-[[VER]].iso"

class CachyOS(GenericUpdater):
    """
    A class representing an updater for CachyOS.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download
        download_page (requests.Response): The HTTP response containing the download page HTML.
        soup_download_page (BeautifulSoup): The parsed HTML content of the download page.

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, edition: str) -> None:
        self.valid_editions = ["desktop", "handheld"]
        self.edition = edition.lower()

        file_path = folder_path / FILE_NAME
        super().__init__(file_path)

        if self.edition not in self.valid_editions:
            raise ValueError(f"Invalid edition: {self.edition}. Valid editions are: {self.valid_editions}")

        self.download_page = requests.get(f"{DOWNLOAD_PAGE_URL}/{self.edition}")
        if self.download_page.status_code != 200:
            raise ConnectionError(f"Failed to fetch the download page from '{DOWNLOAD_PAGE_URL}/{self.edition}'")

        self.soup_download_page = BeautifulSoup(self.download_page.content, features="html.parser")

    @cache
    def _get_download_link(self) -> str:
        latest_version = self._get_latest_version()
        return f"{DOWNLOAD_PAGE_URL}/{self.edition}/{latest_version}/cachyos-{self.edition}-linux-{latest_version}.iso"

    def check_integrity(self) -> bool:
        sha256_url = f"{self._get_download_link()}.sha256"
        sha256_sums = requests.get(sha256_url).text
        sha256_sum = self._parse_sha256_hash(sha256_sums, f"cachyos-{self.edition}-linux-{self._get_latest_version()}.iso")
        return sha256_hash_check(self._get_complete_normalized_file_path(absolute=True), sha256_sum)

    def _parse_sha256_hash(self, hash_file_content: str, filename: str) -> str:
        for line in hash_file_content.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == filename:
                return parts[0]
        raise ValueError(f"Hash not found for the specified file: {filename}")

    @cache
    def _get_latest_version(self) -> str:
        # Find all <a> tags within the table rows
        download_links = self.soup_download_page.select("table#list tbody tr td.link a")
        if not download_links:
            raise VersionNotFoundError("We were not able to parse the download page")

        # Extract version numbers from the href attributes
        version_numbers = [
            link.get("title")
            for link in download_links
            if re.match(r"\d{6}/", link.get("href"))
        ]

        if not version_numbers:
            raise VersionNotFoundError("No valid version numbers found in the download links")

        latest_version = max(version_numbers)
        return latest_version