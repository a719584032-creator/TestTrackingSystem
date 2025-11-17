import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ENDPOINT = "https://oss4.xcloud.lenovo.com:10443"


def create_s3_client():
    session = boto3.session.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or "A003863_Testing",
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or "b2BktcdB6BnMaJueO/ZNJ0QrpUPWcffgY4engwXT",
        region_name=os.getenv("AWS_REGION_NAME", "us-east-1"),
    )

    cfg = Config(
        signature_version="s3v4",
        s3={
            "addressing_style": "path",
            "use_accelerate_endpoint": False,
            "payload_signing_enabled": True,
        }
    )

    return session.client("s3", endpoint_url=ENDPOINT, config=cfg)


def upload_file_simple(s3_client, file_path, bucket, key):
    """使用 put_object 直接上传文件"""
    try:
        # 读取整个文件到内存
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # 获取文件大小
        file_size = len(file_data)

        # 确定 Content-Type
        if file_path.lower().endswith('.png'):
            content_type = "image/png"
        elif file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
            content_type = "image/jpeg"
        else:
            content_type = "application/octet-stream"

        # 使用 put_object 上传
        response = s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_data,
            # ContentType=content_type,
            # ContentLength=file_size
        )

        print(f"文件上传成功: {key}")
        print(f"ETag: {response.get('ETag', 'N/A')}")
        return True

    except ClientError as e:
        print(f"上传失败: {e}")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        return False


def download_file(s3_client, bucket, key, local_path):
    """从 S3 下载文件"""
    try:
        s3_client.download_file(bucket, key, local_path)
        print(f"文件下载成功: {local_path}")
        return True
    except ClientError as e:
        print(f"下载失败: {e}")
        return False


def generate_presigned_url(s3_client, bucket, key, expiration=3600):
    """生成预签名 URL"""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        print(f"预签名 URL: {url}")
        return url
    except ClientError as e:
        print(f"生成 URL 失败: {e}")
        return None


def list_objects(s3_client, bucket, prefix=""):
    """列出对象"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix
        )

        if 'Contents' in response:
            print(f"找到 {len(response['Contents'])} 个对象:")
            for obj in response['Contents']:
                print(f"  {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("没有找到对象")
    except ClientError as e:
        print(f"列出对象失败: {e}")


# 使用示例
if __name__ == "__main__":
    s3 = create_s3_client()
    bucket = 'tts-test'

    # 1. 上传文件 - 使用简单的 put_object 方法
    file_path = r"C:\Users\71958\Pictures\2.png"
    key = "uploads/images/2.png"

    if upload_file_simple(s3, file_path, bucket, key):  # 注意这里改成了 upload_file_simple
        # 2. 生成预签名 URL
        url = generate_presigned_url(s3, bucket, key)

        # 3. 列出上传的文件
        list_objects(s3, bucket, "uploads/")

        # 4. 下载文件（可选）
        # download_file(s3, bucket, key, "downloaded_2.png")
