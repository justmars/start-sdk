from pathlib import Path
from pydantic import BaseSettings, Field
import boto3


class CFR2(BaseSettings):
    """
    _CFR2_

    Cloudflare R2 via Amazon S3 [API](https://developers.cloudflare.com/r2/examples/boto3/)

    Add secrets to .env file:

    Field in .env | Cloudflare API Credential | Where credential found
    :--|:--:|:--
    `CF_R2_ACCT_ID` | Account ID | `https://dash.cloudflare.com/<acct_id>/r2`
    `CF_R2_REGION` | Default Region: `apac` | See [options](https://developers.cloudflare.com/r2/learning/data-location/#available-hints)
    `AWS_ACCESS_KEY_ID` | Key | When R2 Token created in `https://dash.cloudflare.com/<acct_id>/r2/overview/api-tokens`
    `AWS_SECRET_ACCESS_KEY` | Secret | When R2 Token created in `https://dash.cloudflare.com/<acct_id>/r2/overview/api-tokens`

    Examples:
        >>> import os
        >>> os.environ['CF_R2_ACCT_ID'] = "ACT"
        >>> os.environ['AWS_ACCESS_KEY_ID'] = "ABC"
        >>> os.environ['AWS_SECRET_ACCESS_KEY'] = "XYZ"
        >>> from start_sdk import CFR2
        >>> r2 = CFR2()
        >>> type(r2.resource)
        <class 'boto3.resources.factory.s3.ServiceResource'>

    """  # noqa: E501

    region: str = Field(default="apac", repr=True, env="CF_R2_REGION")
    acct: str = Field(default="ACT", repr=False, env="CF_R2_ACCT_ID")
    key: str = Field(default="ABC", repr=False, env="AWS_ACCESS_KEY_ID")
    token: str = Field(default="XYZ", repr=False, env="AWS_SECRET_ACCESS_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def endpoint_url(self):
        return f"https://{self.acct}.r2.cloudflarestorage.com"

    @property
    def resource(self):
        """Resource can be used as a means to access the bucket via an instantiated
        `r2`, e.g. `r2.resource.Bucket('<created-bucket-name>')`
        """
        return boto3.resource(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.key,
            aws_secret_access_key=self.token,
            region_name=self.region,
        )

    def get_bucket(self, bucket_name: str):
        return self.resource.Bucket(bucket_name)  # type: ignore


class CFR2_Bucket(CFR2):
    """
    _CFR2_Bucket_

    Helper function that can be assigned to each bucket.

    Examples:
        >>> import os
        >>> os.environ['CF_R2_ACCT_ID'] = "ACT"
        >>> os.environ['AWS_ACCESS_KEY_ID'] = "ABC"
        >>> os.environ['AWS_SECRET_ACCESS_KEY'] = "XYZ"
        >>> from start_sdk import CFR2_Bucket
        >>> obj = CFR2_Bucket(name='test')
        >>> type(obj.bucket)
        <class 'boto3.resources.factory.s3.Bucket'>
    """

    name: str

    @property
    def bucket(self):
        return self.get_bucket(self.name)

    def upload(self, file_like: str | Path, loc: str, args: dict = {}):
        """Upload local `file_like` contents to r2-bucket path `loc`.

        Args:
            file_like (str | Path): Local file
            loc (str): Remote location
            args (dict, optional): Will populate `ExtraArgs` during upload.
                Defaults to {}.
        """
        with open(file_like, "rb") as read_file:
            return self.bucket.upload_fileobj(read_file, loc, ExtraArgs=args)

    def download(self, loc: str, local_file: str):
        """With a r2-bucket `loc`, download contents to `local_file`.

        Args:
            loc (str): Origin file to download
            local_file (str): Where to download, how to name downloaded file
        """
        with open(local_file, "wb") as write_file:
            return self.bucket.download_fileobj(loc, write_file)
