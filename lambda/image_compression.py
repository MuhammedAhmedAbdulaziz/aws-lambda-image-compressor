import boto3
from PIL import Image
import io
import os
import uuid
from datetime import datetime

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
metadata_table = dynamodb.Table("ImageMetadata")

SOURCE_BUCKET = "source-image-azoz"
DEST_BUCKET = "resized-image-azoz"

def lambda_handler(event, context):
    for record in event['Records']:
        key = record['s3']['object']['key']
        bucket = record['s3']['bucket']['name']

        if bucket != SOURCE_BUCKET:
            continue

        # Download object into memory
        obj = s3.get_object(Bucket=bucket, Key=key)
        img_data = obj["Body"].read()

        # Open image with Pillow
        image = Image.open(io.BytesIO(img_data))

        # Compress + resize (optional)
        image.thumbnail((1024, 1024))  # maintain aspect ratio

        # Save compressed image into memory
        output_buffer = io.BytesIO()
        image.save(output_buffer, format=image.format, optimize=True, quality=70)
        output_buffer.seek(0)

        # Upload compressed image
        output_key = f"resized-{os.path.basename(key)}"
        s3.put_object(
            Bucket=DEST_BUCKET,
            Key=output_key,
            Body=output_buffer,
            ContentType=obj["ContentType"]
        )

        # Save metadata (note the key: imageId)
        metadata_table.put_item(
            Item={
                "imageId": str(uuid.uuid4()),  # must match the partition key name
                "sourceBucket": bucket,
                "sourceKey": key,
                "destBucket": DEST_BUCKET,
                "destKey": output_key,
                "contentType": obj["ContentType"],
                "sizeOriginal": obj["ContentLength"],
                "resizedAt": datetime.utcnow().isoformat()
            }
        )

    return {"status": "done"}