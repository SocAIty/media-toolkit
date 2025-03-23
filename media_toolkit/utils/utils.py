from urllib.parse import urlparse, urlunparse
import httpx
import tqdm
from typing import Union, Tuple, Optional, BinaryIO
from io import BytesIO
import os
import re


def _extract_filename_from_response(response, download_url: str) -> str:
    """Extract filename from response headers or URL path."""
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        file_name_match = re.findall('filename="(.+)"', content_disposition)
        if file_name_match:
            return file_name_match[0]

    # Default to URL path basename if header extraction fails
    return os.path.basename(urlparse(download_url).path)


def _download_file(
        download_url: str,
        save_path: Optional[str] = None,
        silent: bool = True,
        timeout: int = 30,
        chunk_size: int = 8192
) -> Tuple[Union[str, BytesIO], str]:
    """
    Downloads a file from the given URL and saves it to the specified path with a progress bar.

    Args:
        download_url (str): The URL of the file to download.
        save_path (Optional[str]):
            If None: write to a BytesIO object.
            If str: The local file path to save the downloaded file.
        silent (bool): Whether to suppress the download progress bar. Defaults to True.
        timeout (int): Request timeout in seconds. Defaults to 30.
        chunk_size (int): Size of chunks for streaming download. Defaults to 8192.

    Returns:
        A tuple containing the path to the downloaded file or the BytesIO object, and the original file name.
    """
    headers = {"User-Agent": "media-toolkit"}

    with httpx.stream("GET", download_url, headers=headers, timeout=timeout) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0)) or None

        # Determine destination - file or BytesIO
        destination = open(save_path, "wb") if save_path else BytesIO()

        # Handle download with progress bar
        try:
            with tqdm.tqdm(
                    total=total, unit="B", unit_scale=True,
                    disable=silent, desc=f"Downloading {os.path.basename(download_url)}"
            ) as progress_bar:
                for chunk in response.iter_bytes(chunk_size=chunk_size):
                    destination.write(chunk)
                    if total:
                        progress_bar.update(len(chunk))

            # Get original filename
            filename = _extract_filename_from_response(response, download_url)

            # Handle BytesIO case
            if not save_path:
                destination.seek(0)
                return destination, filename

            # Handle file path case
            return save_path, filename
        finally:
            # Close file handle if it's a file (not BytesIO)
            if save_path and not destination.closed:
                destination.close()


def download_file(
        download_url: str,
        save_path: Optional[str] = None,
        silent: bool = True,
        timeout: int = 30,
        chunk_size: int = 8192
) -> Tuple[Union[str, BytesIO], str]:
    """
    Downloads a file from the given URL and saves it to the specified path with a progress bar.

    Args:
        download_url (str): The URL of the file to download.
        save_path (Optional[str]):
            If None: write to a BytesIO object.
            If str: The local file path to save the downloaded file.
        silent (bool): Whether to suppress the download progress bar. Defaults to True.
        timeout (int): Request timeout in seconds. Defaults to 30.
        chunk_size (int): Size of chunks for streaming download. Defaults to 8192.

    Returns:
        A tuple containing the path to the downloaded file or the BytesIO object, and the original file name.
    """
    try:
        return _download_file(download_url, save_path, silent, timeout, chunk_size)
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code

        if status_code == 404:
            raise Exception(f"Failed to download file: {download_url}. File not found.")

        if status_code in (401, 403):
            # Try without query parameters for auth errors
            try:
                parsed_url = urlparse(download_url)
                stripped_url = urlunparse(parsed_url._replace(query=""))
                return _download_file(stripped_url, save_path, silent, timeout, chunk_size)
            except Exception:
                raise Exception(f"Failed to download file: {download_url}. Access permission denied.")

        raise Exception(f"Failed to download file: {download_url}. HTTP error {status_code}.")
    except Exception as e:
        raise Exception(f"Failed to download file: {download_url}. Error: {e}")