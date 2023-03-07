import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
import yaml
from loguru import logger
from pydantic import BaseSettings, Field


class CFR2(BaseSettings):
    """
    _CFR2_

    Cloudflare R2 via Amazon S3 [API](https://developers.cloudflare.com/r2/examples/boto3/).


    The Cloudflare R2 key/secret follows AWS S3 conventions, see compatability in docs..

    Add secrets to .env file:

    Field in .env | Cloudflare API Credential | Where credential found
    :--|:--:|:--
    `CF_ACCT_ID` | Account ID | `https://dash.cloudflare.com/<acct_id>/r2`
    `CF_R2_REGION` | Default Region: `apac` | See [options](https://developers.cloudflare.com/r2/learning/data-location/#available-hints)
    `R2_ACCESS_KEY_ID` | Key | When R2 Token created in `https://dash.cloudflare.com/<acct_id>/r2/overview/api-tokens`
    `R2_SECRET_ACCESS_KEY` | Secret | When R2 Token created in `https://dash.cloudflare.com/<acct_id>/r2/overview/api-tokens`

    Examples:
        >>> import os
        >>> os.environ['CF_ACCT_ID'] = "ACT"
        >>> os.environ['R2_ACCESS_KEY_ID'] = "ABC"
        >>> os.environ['R2_SECRET_ACCESS_KEY'] = "XYZ"
        >>> from start_sdk import CFR2
        >>> r2 = CFR2()
        >>> type(r2.resource)
        <class 'boto3.resources.factory.s3.ServiceResource'>

    """  # noqa: E501

    acct: str = Field(default="ACT", repr=False, env="CF_ACCT_ID")
    r2_region: str = Field(default="apac", repr=True, env="CF_R2_REGION")
    r2_access_key: str = Field(
        default="ABC",
        repr=False,
        title="R2 Key",
        description=(  # noqa: E501
            "The Cloudflare R2 key/secret follows AWS S3 conventions, see"
            " compatability in docs."
        ),
        env="R2_ACCESS_KEY_ID",
    )
    r2_secret_key: str = Field(
        default="XYZ",
        repr=False,
        title="R2 Secret",
        description=(  # noqa: E501
            "The Cloudflare R2 key/secret follows AWS S3 conventions, see"
            " compatability in docs."
        ),
        env="R2_SECRET_ACCESS_KEY",
    )

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
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            region_name=self.r2_region,
        )

    def get_bucket(self, bucket_name: str):
        return self.resource.Bucket(bucket_name)  # type: ignore


class CFR2_Bucket(CFR2):
    """
    _CFR2_Bucket_

    Helper function that can be assigned to each bucket.

    Note [AWS API reference](https://docs.aws.amazon.com/AmazonS3/latest/API) vs. [R2](https://developers.cloudflare.com/r2/data-access/s3-api/api/)

    Examples:
        >>> import os
        >>> os.environ['CF_R2_ACCT_ID'] = "ACT"
        >>> os.environ['R2_ACCESS_KEY_ID'] = "ABC"
        >>> os.environ['R2_SECRET_ACCESS_KEY'] = "XYZ"
        >>> from start_sdk import CFR2_Bucket
        >>> obj = CFR2_Bucket(name='test')
        >>> type(obj.bucket)
        <class 'boto3.resources.factory.s3.Bucket'>
    """  # noqa: E501

    name: str

    @property
    def bucket(self):
        return self.get_bucket(self.name)

    @property
    def client(self):
        return self.bucket.meta.client

    def filter(self, prefix: str, key: str | None = None) -> Iterator[str]:
        """See modified recipe from boto3 re: [filtering](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/collections.html#filtering). Fetches objects in the bucket based on the `prefix` supplied. If a `key` is supplied with the `prefix`, a secondary filter is applied.

        Args:
            prefix (str): Main filter.
            key (str | None, optional): Secondary filter. Defaults to None.

        Yields:
            Iterator[str]: The keys from the bucket matching prefix and key.
        """  # noqa: E501
        objs = self.bucket.objects.filter(Prefix=prefix)
        for obj in objs:
            if key:
                if key in obj.key:
                    yield obj.key
            else:
                yield obj.key

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

    def get_root_prefixes(self):
        """See adapted recipe from boto3 re: top-level [prefixes](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#list-top-level-common-prefixes-in-amazon-s3-bucket).

        Returns:
            list[str]: Matching prefixes in the root of the bucket.
        """  # noqa: E501
        _objs = []
        paginator = self.client.get_paginator("list_objects")
        result = paginator.paginate(Bucket=self.name, Delimiter="/")
        for prefix in result.search("CommonPrefixes"):
            _objs.append(prefix.get("Prefix"))  # type: ignore
        return _objs


class StorageUtils(CFR2_Bucket):
    temp_folder: Path

    @classmethod
    def clean_extra_meta(cls, text: str):
        """S3 metadata can only contain ASCII characters.

        The overall size cannot exceed a certain threshold, see `when calling the PutObject operation: Your metadata headers exceed the maximum allowed metadata size.')`

        Examples:
            >>> bad_text = "Hello,\\n\\n\\nthis breaks"
            >>> StorageUtils.clean_extra_meta(bad_text)
            'Hello, this breaks'
            >>> long_text = "Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Aenean commodo ligula eget dolor. Aenean massa. Cum sociis natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Donec quam felis, ultricies nec, pellentesque eu, pretium quis, sem. Nulla consequat massa quis enim. Donec."
            >>> StorageUtils.clean_extra_meta(long_text)
            'Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Aenean commodo ligula eget dolor. Aenean m'
            >>> valid_text = "This is a valid string"
            >>> StorageUtils.clean_extra_meta(valid_text)
            'This is a valid string'

        """  # noqa: E501
        text = re.sub(r"(\r|\n)+", r" ", text)
        text = re.sub(r"[^\x00-\x7f]", r"", text)
        if len(text) >= 100:
            text = text[:100]
        return text

    @classmethod
    def set_extra_meta(cls, data: dict) -> dict:
        """S3 metadata can be attached as extra args to R2.

        Examples:
            >>> test = {"statute_category": "RA", "statute_serial": None}
            >>> StorageUtils.set_extra_meta(test)
            {'Metadata': {'statute_category': 'RA'}}

        Args:
            data (dict): ordinary dict

        Returns:
            dict: Will be added to the `extra_args` field when uploading to R2
        """
        return {
            "Metadata": {
                k: cls.clean_extra_meta(str(v)) for k, v in data.items() if v
            }
        }

    def make_temp_yaml_path_from_data(self, data: dict) -> Path:
        """Create a temporary yaml file into folder path.

        Args:
            data (dict): What to store in the yaml file

        Returns:
            Path: Location of the yaml file created
        """
        temp_path = self.temp_folder / "temp.yaml"
        temp_path.unlink(missing_ok=True)  # delete existing content, if any.
        with open(temp_path, "w+"):
            temp_path.write_text(yaml.safe_dump(data))
        return temp_path

    def restore_temp_yaml(self, yaml_suffix: str) -> dict[str, Any] | None:
        """Based on the `yaml_suffix`, download the same into a temp file
        and return its contents based on the extension.

        A `yaml` extension should result in contents in `dict` format;

        The temp file is deleted after every successful extraction of
        the `src` as content."""
        if not yaml_suffix.endswith(".yaml"):
            logger.error(f"Not {yaml_suffix=}")
            return None
        path = self.temp_folder / "temp.yaml"

        try:
            self.download(loc=yaml_suffix, local_file=str(path))
        except Exception as e:
            logger.error(f"Could not download yaml; {e=}")
            return None

        content = yaml.safe_load(path.read_bytes())
        path.unlink(missing_ok=True)
        return content

    def restore_temp_txt(self, readable_suffix: str) -> str | None:
        """Based on the `src` prefix, download the same into a temp file
        and return its contents based on the extension.

        An `md` or `html` extension results in `str`.

        The temp file is deleted after every successful extraction of
        the `src` as content."""
        if readable_suffix.endswith(".html"):
            ext = ".html"
        elif readable_suffix.endswith(".md"):
            ext = ".md"
        else:
            logger.error(f"Not {readable_suffix=}")
            return None

        path = self.temp_folder / f"temp{ext}"
        try:
            self.download(loc=readable_suffix, local_file=str(path))
        except Exception as e:
            logger.error(f"Could not download yaml; {e=}")
            return None

        content = path.read_text()
        path.unlink(missing_ok=True)
        return content
