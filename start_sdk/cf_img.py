from pydantic import BaseSettings, Field
import httpx


class CFImage(BaseSettings):
    """
    # Cloudflare [Images](https://developers.cloudflare.com/images/cloudflare-images/) API v4

    Add secrets to .env file:

    Field in .env | Cloudflare API Credential | Where credential found
    :--|:--:|:--
    `CF_IMG_ACCT` | Account ID | `https://dash.cloudflare.com/<acct_id>/images/images`
    `CF_IMG_TOKEN` | Account Hash | `https://dash.cloudflare.com/<acct_id>/images/images`

    Examples:
        >>> from pathlib import Path
        >>> import os
        >>> import io
        >>> os.environ['CF_ACCT_ID'] = "ABC"
        >>> os.environ['CF_IMG_TOKEN'] = "XYZ"
        >>> from start_sdk import CFImage
        >>> cf = CFImage()
        >>> cf.headers
        {'Authorization': 'Bearer XYZ'}
        >>> cf.base
        'https://api.cloudflare.com/client/v4/accounts/ABC/images/v1'
        >>> p = Path().cwd() / "img" / "screenshot.png"
        >>> p.exists() # Sample image found in `/img/screenshot.png`
        True
        >>> img = io.BytesIO(p.read_bytes())
        >>> type(img)
        <class '_io.BytesIO'>
        >>> # Can now use img in `cf.post('sample_id', img)`
    """  # noqa: E501

    acct: str = Field(default="ABC", repr=False, env="CF_ACCT_ID")
    token: str = Field(default="XYZ", repr=False, env="CF_IMG_TOKEN")
    timeout: int = Field(default=60)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    @property
    def base(self):
        return f"https://api.cloudflare.com/client/v4/accounts/{self.acct}/images/v1"

    def get(self, img_id: str) -> httpx.Response:
        """See Cloudflare docs for [serve images](https://developers.cloudflare.com/images/cloudflare-images/serve-images/)"""  # noqa: E501
        with httpx.Client(timeout=self.timeout) as client:
            return client.get(
                url=f"{self.base}/{img_id}", headers=self.headers
            )

    def delete(self, img_id: str) -> httpx.Response:
        """See Cloudflare docs for [delete images](https://developers.cloudflare.com/images/cloudflare-images/transform/delete-images/)"""  # noqa: E501
        with httpx.Client(timeout=self.timeout) as client:
            return client.delete(
                url=f"{self.base}/{img_id}", headers=self.headers
            )

    def post(self, img_id: str, img: bytes) -> httpx.Response:
        """See Cloudflare docs for [upload via url](https://developers.cloudflare.com/images/cloudflare-images/upload-images/upload-via-url/)"""  # noqa: E501
        with httpx.Client(timeout=self.timeout) as client:
            return client.post(
                url=self.base,
                headers=self.headers,
                data={"id": img_id},
                files={"file": (img_id, img)},
            )
