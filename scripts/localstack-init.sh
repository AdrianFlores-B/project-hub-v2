#!/bin/bash
# runs inside the localstack container once it is ready
set -e

awslocal s3 mb s3://projecthub-documents

# package and register the size-calculator lambda
cd /opt/lambdas/size_calculator
python3 -m zipfile -c /tmp/size_calculator.zip handler.py

awslocal lambda create-function \
  --function-name project-size-calculator \
  --runtime python3.12 \
  --handler handler.handler \
  --zip-file fileb:///tmp/size_calculator.zip \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --timeout 30 \
  --environment "Variables={BUCKET=projecthub-documents,API_BASE_URL=http://host.docker.internal:8000,INTERNAL_TOKEN=dev-internal-token}"

awslocal lambda wait function-active-v2 --function-name project-size-calculator

# fire the lambda on every object created or removed in the bucket
awslocal s3api put-bucket-notification-configuration \
  --bucket projecthub-documents \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [{
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:000000000000:function:project-size-calculator",
      "Events": ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"]
    }]
  }'

echo "localstack init done: bucket + size-calculator lambda ready"
