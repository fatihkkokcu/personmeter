import boto3
from botocore.config import Config
from django.conf import settings
from django.core.files.storage import default_storage

def get_s3_presigned_url(image_path, expiration=3600):
    """
    Generate a presigned URL for the S3 object
    :param image_path: Path of the image in S3 bucket (e.g., 'person_images/image.jpg')
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL string
    """
    storage_config = settings.STORAGES.get("default", {})
    storage_options = storage_config.get("OPTIONS", {})

    if storage_config.get("BACKEND") != "storages.backends.s3.S3Storage":
        return default_storage.url(image_path)

    required_keys = ("access_key", "secret_key", "region_name", "bucket_name")
    if any(not storage_options.get(key) for key in required_keys):
        return default_storage.url(image_path)

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=storage_options["access_key"],
        aws_secret_access_key=storage_options["secret_key"],
        region_name=storage_options["region_name"],
        config=Config(signature_version="s3v4"),
    )
    
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": storage_options["bucket_name"],
                "Key": image_path,
            },
            ExpiresIn=expiration,
        )
        return url
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return default_storage.url(image_path)
