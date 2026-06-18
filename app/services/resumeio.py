import io
from dataclasses import dataclass
from datetime import datetime, timezone

import pytesseract
import requests
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader, PdfWriter

from app.schemas.resumeio import Extension


@dataclass
class ResumeioDownloader:
    """
    Class to download a resume from resume.io and convert it to a PDF.

    Parameters
    ----------
    rendering_token : str
        Rendering Token of the resume to download.
    extension : Extension, optional
        Image extension to download, by default "jpeg".
    image_size : int, optional
        Size of the images to download, by default 2000.
    """

    rendering_token: str
    extension: Extension = Extension.jpeg
    image_size: int = 2000
    IMAGES_URL: str = (
        "https://ssr.resume.tools/to-image/{rendering_token}-{page_id}.{extension}?cache={cache_date}&size={image_size}"
    )

    def __post_init__(self) -> None:
        """Set the cache date to the current time."""
        self.cache_date = datetime.now(timezone.utc).isoformat()[:-10] + "Z"

    def generate_pdf(self) -> bytes:
        """
        Generate a PDF from the resume.io resume.

        Returns
        -------
        bytes
            PDF representation of the resume.
        """
        images = self.__download_images()
        pdf = PdfWriter()
        for image in images:
            page_pdf = pytesseract.image_to_pdf_or_hocr(Image.open(image), extension="pdf", config="--dpi 300")
            pdf.add_page(PdfReader(io.BytesIO(page_pdf)).pages[0])
        with io.BytesIO() as file:
            pdf.write(file)
            return file.getvalue()

    def __download_images(self) -> list[io.BytesIO]:
        """Download all page images of the resume by probing until a non-200 response.

        Returns
        -------
        list[io.BytesIO]
            List of image files, one per page.
        """
        images = []
        page_id = 1
        while True:
            image_url = self.IMAGES_URL.format(
                rendering_token=self.rendering_token,
                page_id=page_id,
                extension=self.extension.value,
                cache_date=self.cache_date,
                image_size=self.image_size,
            )
            response = requests.get(
                image_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36",
                },
            )
            if response.status_code != 200:
                break
            images.append(io.BytesIO(response.content))
            page_id += 1
        if not images:
            raise HTTPException(
                status_code=404,
                detail=f"Unable to download resume (rendering token: {self.rendering_token})",
            )
        return images
