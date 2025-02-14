import httpx
import tqdm
from typing import Union
from io import BytesIO


def download_file(
        download_url: str,
        save_path: str = None,
        silent: bool = True,
        timeout: int = 30,
        chunk_size: int = 8192
) -> Union[str, BytesIO]:
    """
    Downloads a file from the given URL and saves it to the specified path with a progress bar.

    Args:
        download_url (str): The URL of the file to download.
        save_path (Optional[str]):
            If None: write to a BytesIO object.
            If str: The local file path to save the downloaded file.
        timeout (int, optional): Request timeout in seconds. Defaults to 30.
        silent (bool, optional): Whether to suppress the download progress bar. Defaults to True.
        chunk_size (int, optional): Size of chunks for streaming download. Defaults to 8192.

    Returns:
        Union[str, BytesIO]: The path to the downloaded file or the BytesIO object.
    """
    try:
        with httpx.stream("GET", download_url, timeout=timeout) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0)) or None

            destination = open(save_path, "wb") if save_path else BytesIO()

            with destination as file, tqdm.tqdm(
                    total=total, unit="B", unit_scale=True, disable=silent, desc=f"Downloading {download_url}"
            ) as progress_bar:
                for chunk in response.iter_bytes(chunk_size=chunk_size):
                    file.write(chunk)
                    if total:
                        progress_bar.update(len(chunk))

            if isinstance(destination, BytesIO):
                destination.seek(0)
                return destination
            return save_path
    except httpx.HTTPError as e:
        raise RuntimeError(f"Download failed: {e}")

