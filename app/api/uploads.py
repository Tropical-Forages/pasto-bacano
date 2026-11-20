"""Files sent with a web chat message, turned into Semente media.

The website sends ``files: [{name, mime_type, content_base64}]``. Photos become
``Image`` objects (Semente describes them for the agent); farm boundaries
(GeoJSON, JSON, KML, KMZ, zipped shapefile) become ``File`` objects, which
Semente converts to GeoJSON for registration. Other formats (GPX, PDF) are not
read yet: they are dropped and a note tells the agent, so it can explain which
formats work.
"""

import base64
import binascii
from dataclasses import dataclass, field
from pathlib import Path

from semente.tools.types import File, Image

IMAGE_EXTENSIONS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
BOUNDARY_EXTENSIONS = {".geojson", ".json", ".kml", ".kmz", ".zip"}
MAX_FILE_BYTES = 5 * 1024 * 1024

UNSUPPORTED_NOTE = (
    "[FILE]The user sent the file \"{name}\", which this channel cannot read yet. "
    "Farm boundaries are accepted as GeoJSON, KML, KMZ or a zipped shapefile, and photos as JPG or PNG.[/FILE]"
)


@dataclass
class Uploads:
    """Media for ``Harness.run`` plus notes for files that were not used."""

    images: list = field(default_factory=list)
    files: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def caption(self) -> str:
        """Text for a message sent with files but no words (the model input can't be empty)."""
        if self.files:
            names = ", ".join(f.filename for f in self.files)
            return f"I am sending the boundary of my property in the attached file ({names})."
        if self.images:
            return "I am sending a photo."
        return ""


def read_uploads(items: list) -> Uploads:
    """Decodes the uploaded files of one message.

    Args:
        items (list): ``InputFile`` objects from the request.

    Returns:
        Uploads: Images, boundary files and notes about unsupported files.

    Raises:
        ValueError: When a file is not valid base64 or is too large.
    """
    uploads = Uploads()
    for item in items:
        try:
            content = base64.b64decode(item.content_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError(f"File {item.name} is not valid base64.") from error
        if len(content) > MAX_FILE_BYTES:
            raise ValueError(f"File {item.name} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")

        name = Path(item.name).name or "file"
        suffix = Path(name).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            uploads.images.append(Image(content=content, mime_type=IMAGE_EXTENSIONS[suffix], format=suffix[1:]))
        elif suffix in BOUNDARY_EXTENSIONS:
            uploads.files.append(
                File(content=content, filename=name, name=name, mime_type=item.mime_type or None, size=len(content))
            )
        else:
            uploads.notes.append(UNSUPPORTED_NOTE.format(name=name))
    return uploads
