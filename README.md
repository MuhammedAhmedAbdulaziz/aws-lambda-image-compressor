## 📦 AWS Lambda Image Compression & Metadata Storage

This project provides a serverless solution for automatically compressing images uploaded to an Amazon S3 bucket and storing their metadata in a DynamoDB table using an AWS Lambda function.

---

### ✅ Features
- Compresses uploaded images using Pillow.
- Resizes images to a max of 1024x1024 while maintaining aspect ratio.
- Stores compressed images in a destination S3 bucket.
- Saves image metadata (source, destination, size, type, timestamp) in DynamoDB.

---

## 🛠️ Prerequisites
- AWS CLI configured
- Docker installed (for building Lambda layer)
- IAM permissions to deploy Lambda, S3, and DynamoDB

---

## 🚧 Step 1: Build the Pillow Lambda Layer

1. Create the folder and requirements file:
   ```bash
   mkdir pillow-layer && cd pillow-layer
   echo "Pillow" > requirements.txt
   ```

2. Build the layer using Docker:
   ```bash
   docker run -v "$PWD":/var/task public.ecr.aws/sam/build-python3.12:1.115.0-x86_64 \
     /bin/sh -c "pip install -r requirements.txt -t python/lib/python3.12/site-packages/; exit"
   ```

3. (Optional) Use prebuilt binary wheels for reliability:
   ```bash
   pip install --platform manylinux2014_x86_64 --only-binary=:all: \
     -t python/lib/python3.12/site-packages/ Pillow
   ```

4. Zip your layer:
   ```bash
   zip -r pillow-layer.zip python
   ```

Upload `pillow-layer.zip` to Lambda > Layers.

---

## 🚀 Step 2: Deploy the Lambda Function

1. Open AWS Lambda Console
2. Create a new function with runtime **Python 3.12**
3. Attach your custom Pillow Layer
4. Paste the contents of `lambda_function.py`
5. Set environment variables if needed (not required here)

---

## 🔐 Step 3: Set IAM Permissions

Your Lambda role must have:
- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` (source and resized buckets)
- `dynamodb:PutItem` for ImageMetadata table

Minimum inline policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::source-image",
        "arn:aws:s3:::source-image/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::resized-image/*"
    },
    {
      "Effect": "Allow",
      "Action": "dynamodb:PutItem",
      "Resource": "arn:aws:dynamodb:eu-west-1:<your-account-id>:table/ImageMetadata"
    }
  ]
}
```

---

## 🧪 Step 4: Test the Workflow

1. Upload an image to `source-image` bucket
2. Verify output in `resized-image`
3. Explore DynamoDB > `ImageMetadata` for entry

---

## 📜 lambda_function.py

```python
import boto3
from PIL import Image
import io
import os
import uuid
from datetime import datetime

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
metadata_table = dynamodb.Table("ImageMetadata")

SOURCE_BUCKET = "source-image"
DEST_BUCKET = "resized-image"

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
```


