import boto3
from django.conf import settings
from botocore.config import Config
import os

def get_s3_presigned_url(image_path, expiration=3600):
    """
    Generate a presigned URL for the S3 object
    :param image_path: Path of the image in S3 bucket (e.g., 'person_images/image.jpg')
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL string
    """
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.STORAGES['default']['OPTIONS']['access_key'],
        aws_secret_access_key=settings.STORAGES['default']['OPTIONS']['secret_key'],
        region_name=settings.STORAGES['default']['OPTIONS']['region_name'],
        config=Config(signature_version='s3v4')
    )
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.STORAGES['default']['OPTIONS']['bucket_name'],
                'Key': image_path
            },
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return None 