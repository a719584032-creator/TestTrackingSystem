import boto3
import os
from datetime import datetime
from botocore.config import Config

# ====== 配置 ======
ACCESS_KEY = "O26GE34VYPCI33U45RJA"
SECRET_KEY = "b2BktcdB6BnMaJueO/ZNJ0QrpUPWcffgY4engwXT"
ENDPOINT_URL = "https://oss4.xcloud.lenovo.com:10443"
REGION = "us-east-1"
BUCKET_NAME = "tts-test"

cfg = Config(
    signature_version="s3v4",
    s3={
        "addressing_style": "path",
        "payload_signing_enabled": True,
    },
    # 关键：避免 botocore 走 trailer/checksum 导致 chunked
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
)

s3 = boto3.client(
    "s3",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    endpoint_url=ENDPOINT_URL,
    region_name=REGION,
    config=cfg,
)
# s3.create_bucket(Bucket=BUCKET_NAME)

local_file = "untitled.ui"
date_prefix = datetime.now().strftime("%Y-%m-%d")
object_key = f"{date_prefix}/{os.path.basename(local_file)}"

# 关键：读成 bytes -> requests 会带 Content-Length，不会 Transfer-Encoding: chunked
with open(local_file, "rb") as f:
    data = f.read()

s3.put_object(
    Bucket=BUCKET_NAME,
    Key=object_key,
    Body=data,
    ContentLength=len(data),
)

print("上传成功：", f"s3://{BUCKET_NAME}/{object_key}")
