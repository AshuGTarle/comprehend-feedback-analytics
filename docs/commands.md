#!/usr/bin/env bash
# Comprehend – Customer Feedback Analytics Platform: Full Setup Script (MacOS)
# This script will guide you through setting up and running the entire project via CLI.
# Each step includes detailed comments explaining the purpose and expected outcome.
# **Important:** Replace placeholder values (like <AWS_ACCOUNT_ID>, <UNIQUE_BUCKET_NAME>, etc.) with your actual values.

# -----------------------------
# Pre-requisites: Tools & AWS Config
# -----------------------------

# 1. Install Homebrew (package manager for MacOS) if not already installed.
#    Homebrew is used to easily install the AWS CLI. Skip this if Homebrew is already present.
#/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Use Homebrew to install the AWS CLI (Command Line Interface).
#    AWS CLI is required to interact with AWS services from your terminal.
brew update                    # Update Homebrew to get the latest formulae
brew install awscli            # Install AWS CLI v2 on MacOS
aws --version                  # Verify the AWS CLI is installed (prints the version if successful)
# Expected output: aws-cli/2.X.Y Python/3.X ... (Confirm that a version is displayed)

# 3. Configure AWS CLI with your credentials and default region.
#    This will prompt for AWS Access Key, Secret Key, and default region (e.g., eu-central-1).
#    Ensure the IAM user/credentials you use have permissions for S3, DynamoDB, Lambda, API Gateway, Cognito, SNS, etc.
aws configure
# When prompted:
# - AWS Access Key ID [None]: (Enter your AWS access key)
# - AWS Secret Access Key [None]: (Enter your AWS secret key)
# - Default region name [None]: (Enter your preferred AWS region, e.g., eu-central-1)
# - Default output format [None]: (Hit enter for default, or type "json")
# After configuring, your credentials are saved in ~/.aws/credentials and region in ~/.aws/config.

# (Alternative: On Windows, download and run the AWS CLI installer from AWS's website, or use "choco install awscli" if using Chocolatey. Then run `aws configure` similarly.)

# 4. Ensure you have the project source code on your local machine.
#    If you haven't already, download or clone the project repository so that you have the following structure:
#    AWS-Feedback-Analytics/
#    ├── frontend/ (contains index.html and admin.html)
#    ├── lambda/   (contains *.py Lambda function code files)
#    ├── docs/     (contains any JSON policy files or test event files)
#    └── ... (README, etc.)
#    Navigate to the project directory:
cd path/to/AWS-Feedback-Analytics

# (If you don't have the code locally, you can clone it if it's in a Git repository, or obtain it from the provided source. Ensure the files are present before proceeding.)

# 5. Export some environment variables for reuse in commands.
#    This makes it easier to reference values like AWS region, account, and unique resource names throughout the script.
export AWS_REGION="eu-central-1"               # set your AWS region (example: eu-central-1 for Frankfurt)
export AWS_ACCOUNT_ID="<AWS_ACCOUNT_ID>"       # replace with your AWS Account ID (needed for ARNs)
export BUCKET_NAME="customer-feedback-<UNIQUE>"# S3 bucket name must be globally unique. e.g., customer-feedback-myname123
# Tip: Use a unique suffix (like your name or initials) in BUCKET_NAME to avoid collisions.
echo "Using AWS region $AWS_REGION and bucket name $BUCKET_NAME"

# -----------------------------
# Step 1: S3 Static Website for Frontend
# -----------------------------
# We will create an S3 bucket to host the frontend web pages (index.html and admin.html).
# This bucket will serve the static website (customer feedback form and admin dashboard).

# 1.1 Create a new S3 bucket for the project (replace <UNIQUE> in BUCKET_NAME if not done already).
aws s3 mb s3://$BUCKET_NAME --region $AWS_REGION
# The above command makes a new bucket. If successful, it prints "make_bucket: <bucket-name>".

# 1.2 Verify the bucket was created by listing all S3 buckets or checking its region.
aws s3 ls             # List buckets to confirm creation (your new bucket should appear)
aws s3api get-bucket-location --bucket $BUCKET_NAME --output text
# Expected output is the region (or null for us-east-1). Make sure it matches $AWS_REGION.

# 1.3 Enable static website hosting on the bucket.
#    This allows the bucket to serve web pages via an endpoint.
aws s3 website s3://$BUCKET_NAME/ --index-document index.html --error-document error.html
# (We specify index.html as the default page. error.html is optional; if not present, a default error page is shown.)

# 1.4 Configure the bucket policy to allow public read access to the website content.
#    We will create a JSON policy file granting read (GetObject) permission to everyone for this bucket.
cat > public-read-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
    }
  ]
}
EOF

# 1.5 Apply the public read policy to the bucket.
aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file://public-read-policy.json

# 1.6 Disable default blocking of public access on the bucket (AWS buckets block public access by default).
aws s3api put-public-access-block --bucket $BUCKET_NAME \
  --public-access-block-configuration '{
    "BlockPublicAcls": false,
    "IgnorePublicAcls": false,
    "BlockPublicPolicy": false,
    "RestrictPublicBuckets": false
  }'
# This ensures the bucket policy we set can actually grant public access.

# 1.7 Upload the frontend files to the S3 bucket.
#    This includes the public feedback form (index.html) and the admin dashboard page (admin.html).
aws s3 cp frontend/index.html s3://$BUCKET_NAME/index.html --region $AWS_REGION
aws s3 cp frontend/admin.html s3://$BUCKET_NAME/admin.html --region $AWS_REGION

# 1.8 (Optional) Upload any additional static assets (CSS, JS, images) if present in frontend/assets.
#aws s3 cp frontend/assets/ s3://$BUCKET_NAME/assets/ --recursive --region $AWS_REGION

# 1.9 Retrieve the S3 website URL for your bucket (the endpoint to access your static site).
website_url="http://$BUCKET_NAME.s3-website.$AWS_REGION.amazonaws.com"
echo "Static website is hosted at: $website_url"
# Note: This is an HTTP endpoint. (For HTTPS, we'll set up CloudFront later.)

# At this point, you have a static website hosted on S3. You can visit the $website_url in a browser.
# However, the forms won’t function yet because we haven’t set up the backend (API, database, Lambdas).

# -----------------------------
# Step 2: DynamoDB Table for Feedback Data
# -----------------------------
# Next, create a DynamoDB table to store customer feedback entries.
# The table will use a composite key: feedback_id (partition key) and date (sort key).

# 2.1 Create the DynamoDB table "CustomerFeedbackAnalysis" with the specified keys.
aws dynamodb create-table \
    --table-name CustomerFeedbackAnalysis \
    --attribute-definitions AttributeName=feedback_id,AttributeType=S AttributeName=date,AttributeType=S \
    --key-schema AttributeName=feedback_id,KeyType=HASH AttributeName=date,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region $AWS_REGION
# We use PAY_PER_REQUEST billing so we don't need to manage capacity units.
# Keys:
#  - feedback_id: Unique identifier for each feedback (String).
#  - date: Timestamp of feedback submission (String, we will store ISO8601 date strings for sorting).

# 2.2 Confirm the table was created and is active.
aws dynamodb list-tables --region $AWS_REGION            # The new table name should appear in the list.
aws dynamodb describe-table --table-name CustomerFeedbackAnalysis --region $AWS_REGION \
  --query "Table.TableStatus" --output text
# Expected output for status is "ACTIVE" once the table is ready (this may take a few seconds).

# 2.3 Enable DynamoDB Streams on the table.
#    This will allow the system to trigger a Lambda when new items are inserted, enabling the sentiment analysis pipeline.
aws dynamodb update-table \
    --table-name CustomerFeedbackAnalysis \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_IMAGE \
    --region $AWS_REGION
# StreamViewType=NEW_IMAGE means the stream will capture the new item entirely on insert.
# After this, the table will have a Stream ARN (Amazon Resource Name) that we need for connecting to Lambda.

# 2.4 Retrieve and store the DynamoDB Stream ARN in a variable for later use.
export DDB_STREAM_ARN=$(aws dynamodb describe-table --table-name CustomerFeedbackAnalysis \
                     --query "Table.LatestStreamArn" --output text --region $AWS_REGION)
echo "DynamoDB Stream ARN: $DDB_STREAM_ARN"
# We'll use $DDB_STREAM_ARN when configuring the Lambda trigger for sentiment analysis.

# -----------------------------
# Step 3: IAM Role for Lambda Functions
# -----------------------------
# AWS Lambda functions need an IAM role with permissions to access other services (DynamoDB, Comprehend, etc.).
# We'll create one IAM role for all our Lambda functions, called "LambdaFeedbackRole".

# 3.1 Define a trust policy that allows Lambda service to assume the role.
#    Save the trust policy JSON to a file.
cat > lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# 3.2 Create the IAM role for Lambda using the trust policy.
aws iam create-role --role-name LambdaFeedbackRole --assume-role-policy-document file://lambda-trust-policy.json
# Expected output: JSON with the new role's ARN. The role is created but has no permissions yet.

# 3.3 Attach necessary AWS managed policies to the role to grant required permissions:
#    - AWSLambdaBasicExecutionRole: Allows writing logs to CloudWatch.
#    - AmazonDynamoDBFullAccess: Allows reading/writing to DynamoDB table (for simplicity, using full access in this demo).
#    - ComprehendFullAccess: Allows using Amazon Comprehend for sentiment analysis.
#    - AmazonSNSFullAccess: Allows publishing to SNS topics (for email alerts on negative feedback).
aws iam attach-role-policy --role-name LambdaFeedbackRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name LambdaFeedbackRole --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
aws iam attach-role-policy --role-name LambdaFeedbackRole --policy-arn arn:aws:iam::aws:policy/ComprehendFullAccess
aws iam attach-role-policy --role-name LambdaFeedbackRole --policy-arn arn:aws:iam::aws:policy/AmazonSNSFullAccess

# (Optional) If your Lambdas need S3 access in the future (e.g., to read/write files), attach AmazonS3ReadOnlyAccess or similar. Not required in this project since our Lambdas don't directly interact with S3.
# aws iam attach-role-policy --role-name LambdaFeedbackRole --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# 3.4 Verify that the policies are attached to the role.
aws iam list-attached-role-policies --role-name LambdaFeedbackRole --output table
# You should see the four policies listed as attached to LambdaFeedbackRole.

# Note: It may take a minute or so for new IAM role and policy attachments to propagate. 
# If subsequent steps fail due to permissions, wait a bit and retry.

# -----------------------------
# Step 4: Deploy Lambda Functions (Backend Logic)
# -----------------------------
# The project has three Lambda functions, all implemented in Python:
#  - SubmitFeedbackFunction (handles feedback submission, writes to DynamoDB)
#  - GetFeedbackFunction    (fetches all feedback from DynamoDB for the admin dashboard)
#  - AnalyzeFeedbackSentiment (processes DynamoDB stream events, calls Comprehend, updates sentiment, and sends SNS alerts)
# We'll package and create each Lambda with the proper configuration.

# 4.1 Package and create SubmitFeedbackFunction
# ---------------------------------------------
# Zip the Lambda function code for submitting feedback.
cd lambda
zip submit_feedback.zip submit_feedback.py
# The above creates submit_feedback.zip containing the code. (Make sure you're in the directory containing submit_feedback.py)

# Create the Lambda function for submitting feedback.
aws lambda create-function --function-name SubmitFeedbackFunction \
  --runtime python3.12 \
  --handler submit_feedback.lambda_handler \
  --role arn:aws:iam::$AWS_ACCOUNT_ID:role/LambdaFeedbackRole \
  --zip-file fileb://submit_feedback.zip \
  --environment Variables="{TABLE_NAME=CustomerFeedbackAnalysis}" \
  --region $AWS_REGION
# Explanation:
#  --runtime python3.12 specifies the Python version for Lambda.
#  --handler submit_feedback.lambda_handler means the function uses lambda_handler function in submit_feedback.py.
#  --role is the ARN of the IAM role we created (with our AWS account ID inserted).
#  --environment sets an environment variable TABLE_NAME used by our code (if the code reads the table name from env).
# If successful, AWS returns a JSON with details of the new Lambda function.

# 4.2 (Optional) Test SubmitFeedbackFunction locally via AWS CLI.
# We can invoke the Lambda with a sample event to ensure it writes to DynamoDB.
# First, create a test event JSON file representing a feedback submission.
cat > test-feedback.json <<EOF
{
  "customer_id": "user123",
  "comment": "The website is very slow and crashes sometimes.",
  "date": "2025-10-01T12:00:00Z"
}
EOF

# Invoke the SubmitFeedbackFunction with the test event.
aws lambda invoke --function-name SubmitFeedbackFunction \
  --cli-binary-format raw-in-base64-out \
  --payload file://test-feedback.json \
  response.json --region $AWS_REGION
# The lambda is invoked asynchronously via CLI, and the response (if any) is saved to response.json.

# Check the Lambda's response output:
cat response.json && echo   # Print the content of response.json
# Expected: It might contain a success message or status code. If our function doesn't return anything specific, it might be empty or just {"statusCode": 200} depending on implementation.

# Verify that the feedback was written to DynamoDB by scanning the table:
aws dynamodb scan --table-name CustomerFeedbackAnalysis --region $AWS_REGION --output json > scan_results.json
cat scan_results.json | python -m json.tool
# Look for an item with customer_id "user123" and the comment provided. The "status" field might be "PENDING" (depending on implementation, since sentiment analysis hasn't run yet).
# If the item is present, the Submit lambda is working as expected. 

# (The status may be PENDING initially, meaning it hasn't been processed by the analysis function yet. We'll set up the analysis Lambda soon.)

# 4.3 Package and create GetFeedbackFunction (for admin dashboard to retrieve data)
# ------------------------------------------------------------------------------
# This function will read all feedback entries from DynamoDB and return them (likely via API Gateway GET).
zip get_feedback.zip get_feedback.py

aws lambda create-function --function-name GetFeedbackFunction \
  --runtime python3.12 \
  --handler get_feedback.lambda_handler \
  --role arn:aws:iam::$AWS_ACCOUNT_ID:role/LambdaFeedbackRole \
  --zip-file fileb://get_feedback.zip \
  --environment Variables="{DDB_TABLE=CustomerFeedbackAnalysis}" \
  --region $AWS_REGION
# Note: We used environment variable DDB_TABLE here (assuming get_feedback.py expects DDB_TABLE for the table name).
# If the code uses a different variable name or hard-codes the table, adjust accordingly. 
# (In our configuration, we've set DDB_TABLE=CustomerFeedbackAnalysis as a safe default for the get function.)

# Verify the GetFeedbackFunction was created:
aws lambda get-function --function-name GetFeedbackFunction --region $AWS_REGION
# This should return configuration details if successful.

# 4.4 Package and create AnalyzeFeedbackSentiment function (for sentiment analysis)
# ------------------------------------------------------------------------------
# This function will be triggered by DynamoDB Streams for new feedback entries.
zip analyze_feedback.zip analyze_feedback.py

aws lambda create-function --function-name AnalyzeFeedbackSentiment \
  --runtime python3.12 \
  --handler analyze_feedback.lambda_handler \
  --role arn:aws:iam::$AWS_ACCOUNT_ID:role/LambdaFeedbackRole \
  --zip-file fileb://analyze_feedback.zip \
  --environment Variables="{TABLE_NAME=CustomerFeedbackAnalysis}" \
  --region $AWS_REGION
# The environment variable TABLE_NAME is used by analyze_feedback.py to know which DynamoDB table to update.
# Verify the function:
aws lambda get-function --function-name AnalyzeFeedbackSentiment --region $AWS_REGION

# (At this stage, we have created all three Lambda functions but we haven't connected them to anything yet. Next, we'll set up API Gateway for the Submit and Get functions, and DynamoDB trigger for the Analyze function.)

# -----------------------------
# Step 5: API Gateway Setup (REST API for Submit and Get)
# -----------------------------
# We will create a REST API with Amazon API Gateway to expose endpoints for submitting feedback and retrieving feedback.
# The API will have a resource "/feedback" with two methods:
#    POST /feedback -> invokes SubmitFeedbackFunction (no auth, public form submission)
#    GET  /feedback -> invokes GetFeedbackFunction (this could be protected by Cognito, but we'll set to open or optional auth for now)

# 5.1 Create a new API Gateway REST API
export API_ID=$(aws apigateway create-rest-api --name "FeedbackAPI" --region $AWS_REGION --query "id" --output text)
echo "Created API Gateway with ID: $API_ID"
# The API_ID (e.g., "abc123defg") uniquely identifies our new API.

# 5.2 Get the root resource ID of the API.
#    The root resource is the base path "/" of the API; we need its ID to create sub-resources.
export ROOT_ID=$(aws apigateway get-resources --rest-api-id $API_ID --region $AWS_REGION \
               --query "items[?path=='/'].id" --output text)
echo "Root resource ID for API: $ROOT_ID"

# 5.3 Create a "/feedback" resource under the root.
export FEEDBACK_ID=$(aws apigateway create-resource --rest-api-id $API_ID --parent-id $ROOT_ID \
                   --path-part feedback --region $AWS_REGION --query "id" --output text)
echo "Created /feedback resource with ID: $FEEDBACK_ID"
# Now we have a resource at path "/feedback".

# 5.4 Set up the POST method on /feedback
#    This method will accept feedback submissions and forward them to our SubmitFeedbackFunction.
aws apigateway put-method --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method POST --authorization-type "NONE" --region $AWS_REGION
# We specify "NONE" for authorization to make this endpoint public (no auth token required) for the feedback form.

# 5.5 Integrate the POST /feedback method with the Lambda (SubmitFeedbackFunction).
aws apigateway put-integration --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method POST --type AWS_PROXY --integration-http-method POST \
  --uri arn:aws:apigateway:$AWS_REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:SubmitFeedbackFunction/invocations \
  --region $AWS_REGION
# This tells API Gateway to proxy incoming POST requests to our Lambda function.
# The URI is in the format required for Lambda proxy integration (note the ARN of our SubmitFeedbackFunction).

# 5.6 Grant API Gateway permission to invoke the SubmitFeedbackFunction.
aws lambda add-permission --function-name SubmitFeedbackFunction \
  --statement-id AllowAPIGatewayInvokePOST \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$AWS_ACCOUNT_ID:$API_ID/*/POST/feedback" \
  --region $AWS_REGION
# This permission allows API Gateway to trigger the Lambda when any stage (*) and any deployment executes POST on /feedback.

# 5.7 Set up the GET method on /feedback (to retrieve all feedback via GetFeedbackFunction).
aws apigateway put-method --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method GET --authorization-type "NONE" --region $AWS_REGION
# Note: In a real scenario, you'd likely secure GET with Cognito auth. We're using NONE for now to simplify, making it public or testable.

aws apigateway put-integration --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method GET --type AWS_PROXY --integration-http-method POST \
  --uri arn:aws:apigateway:$AWS_REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:GetFeedbackFunction/invocations \
  --region $AWS_REGION
# The GET integration is also a Lambda proxy integration to our GetFeedbackFunction.

aws lambda add-permission --function-name GetFeedbackFunction \
  --statement-id AllowAPIGatewayInvokeGET \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$AWS_ACCOUNT_ID:$API_ID/*/GET/feedback" \
  --region $AWS_REGION
# This permission allows API Gateway to invoke the GetFeedbackFunction on GET requests.

# 5.8 Enable CORS (Cross-Origin Resource Sharing) on the API methods.
#    CORS is needed so that our JavaScript running on the static website (S3 domain) can call the API (different domain) in the browser.
#    We'll add an OPTIONS method to /feedback for preflight, and set appropriate headers.

# Create OPTIONS method for /feedback resource.
aws apigateway put-method --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method OPTIONS --authorization-type "NONE" --region $AWS_REGION

# Integrate OPTIONS with a MOCK response (API Gateway will respond to OPTIONS requests without sending to Lambda).
aws apigateway put-integration --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method OPTIONS --type MOCK \
  --request-templates '{"application/json":"{\"statusCode\":200}"}' \
  --region $AWS_REGION

# Enable CORS response headers for the OPTIONS method.
aws apigateway put-method-response --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method OPTIONS --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers":true, "method.response.header.Access-Control-Allow-Methods":true, "method.response.header.Access-Control-Allow-Origin":true}' \
  --response-models '{"application/json":"Empty"}' \
  --region $AWS_REGION

# Prepare integration response parameters with CORS headers (as a JSON file for clarity).
cat > cors-headers.json <<EOF
{
  "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
  "method.response.header.Access-Control-Allow-Methods": "'GET,POST,OPTIONS'",
  "method.response.header.Access-Control-Allow-Origin": "'*'"
}
EOF

# Attach the CORS headers to the OPTIONS integration response.
aws apigateway put-integration-response --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method OPTIONS --status-code 200 \
  --response-parameters file://cors-headers.json \
  --region $AWS_REGION

# For completeness, also enable CORS on the POST and GET methods responses.
# This ensures they return the Access-Control-Allow-Origin header in their responses.
aws apigateway put-method-response --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method POST --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Origin": true}' \
  --response-models '{"application/json":"Empty"}' \
  --region $AWS_REGION

aws apigateway put-integration-response --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method POST --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Origin": "*"}' \
  --region $AWS_REGION

aws apigateway put-method-response --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method GET --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Origin": true}' \
  --response-models '{"application/json":"Empty"}' \
  --region $AWS_REGION

aws apigateway put-integration-response --rest-api-id $API_ID --resource-id $FEEDBACK_ID \
  --http-method GET --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Origin": "*"}' \
  --region $AWS_REGION

# 5.9 Deploy the API to a stage.
#    We'll create a deployment and name the stage "dev" (for development/testing).
aws apigateway create-deployment --rest-api-id $API_ID --stage-name dev --region $AWS_REGION
# After this, the API becomes accessible via an invoke URL.

# Construct the base URL for the API:
API_URL="https://$API_ID.execute-api.$AWS_REGION.amazonaws.com/dev/feedback"
echo "API base URL for /feedback: $API_URL"
# This URL will be used by the frontend to POST and GET feedback. (It's the base, with /feedback resource already included as we created.)

# -----------------------------
# Step 6: Connect Frontend to API & Final Configurations
# -----------------------------
# Now that the backend is up (API and Lambdas), we need to configure our frontend files to use the correct API endpoint (and Cognito details if applicable).

# 6.1 Update the frontend HTML files with the API endpoint and any necessary config.
#    Open frontend/index.html in an editor (or use sed) and find the placeholder or variable for the API URL.
#    For example, if index.html contains something like:
#       const apiUrl = "https://<placeholder>.execute-api.region.amazonaws.com/dev/feedback";
#    Replace it with the actual API URL from above ($API_URL).
#    Similarly, update frontend/admin.html to point to the same API for GET requests.
#    (If the admin.html has placeholders for API endpoint or Cognito User Pool ID/App Client, update those accordingly. For now, if not using Cognito, ensure any such code won't block functionality.)

# Using sed (stream editor) to replace placeholder text in files (if known placeholders exist):
# sed -i '' "s~<API_ENDPOINT_PLACEHOLDER>~$API_URL~g" frontend/index.html
# sed -i '' "s~<API_ENDPOINT_PLACEHOLDER>~$API_URL~g" frontend/admin.html
# (Replace <API_ENDPOINT_PLACEHOLDER> with the actual text that needs replacing if applicable. If the HTML already has the correct endpoint variables, you can skip this.)

# If the admin dashboard requires Cognito config and you intend to use Cognito authentication:
#  - Replace any placeholders for Cognito User Pool ID, App Client ID, and region in admin.html with your Cognito values (we will set up Cognito in an optional step later).
#  - For now, if not using Cognito, you may leave admin.html as-is or ensure it doesn't enforce login.

# Save the changes to index.html and admin.html after inserting the correct API URL (and Cognito info, if used).

# 6.2 Upload the updated HTML files to S3 so the changes take effect.
aws s3 cp frontend/index.html s3://$BUCKET_NAME/index.html --region $AWS_REGION
aws s3 cp frontend/admin.html s3://$BUCKET_NAME/admin.html --region $AWS_REGION

# (If you have CloudFront caching in front of S3 (from a later step), you'd need to invalidate the cache for these files. Since we haven't set up CloudFront yet, this isn't needed now.)

# 6.3 Verify that the static website is now calling the API correctly:
#    You can test by accessing the website and submitting a feedback, or by using curl to simulate the frontend:
curl -i -X POST -H "Content-Type: application/json" \
  -d '{"customer_id":"test123","comment":"Great product, but shipping was slow.","date":"2025-10-02T08:00:00Z"}' \
  $API_URL
# This sends a test feedback submission to our API. The `-i` flag shows response headers along with the body.
# Expected response: an HTTP 200 status and perhaps a confirmation message or the saved item (depending on Lambda implementation).
# If CORS is configured correctly, the response headers should include `Access-Control-Allow-Origin: *`.

# 6.4 Check DynamoDB to ensure the new feedback was stored.
aws dynamodb scan --table-name CustomerFeedbackAnalysis --region $AWS_REGION --projection-expression "feedback_id, date, customer_id, comment, status, sentiment"
# The output should list the items in the table. The newly added item (test123) should be present with status (likely "PENDING" if not yet processed by Comprehend).
# At this moment, sentiment might still be null or not present, since we haven't enabled the analysis trigger yet.

# (If any issues are present at this stage, see the Troubleshooting section at the end. Common issues might include misconfigured API integration or permissions.)

# -----------------------------
# Step 7: Configure DynamoDB Stream -> Lambda Trigger (Sentiment Analysis)
# -----------------------------
# Now we wire up the sentiment analysis Lambda to automatically process new feedback entries via the DynamoDB stream we enabled.
# When a new item is inserted (status PENDING), this Lambda will be invoked to analyze sentiment and update the item.

# 7.1 Create an event source mapping between the DynamoDB stream and the AnalyzeFeedbackSentiment Lambda.
aws lambda create-event-source-mapping \
  --function-name AnalyzeFeedbackSentiment \
  --event-source-arn "$DDB_STREAM_ARN" \
  --starting-position LATEST \
  --batch-size 1 \
  --region $AWS_REGION
# starting-position LATEST means the Lambda will start processing new records that appear after this mapping is created.
# batch-size 1 means process one record at a time (ensures each feedback is processed individually).

# 7.2 Verify the event source mapping was created and is enabled.
aws lambda list-event-source-mappings --function-name AnalyzeFeedbackSentiment --region $AWS_REGION --output table
# You should see the mapping with the DynamoDB stream ARN and a State "Enabled". Note the UUID of the mapping (not usually needed unless troubleshooting).

# 7.3 (Optional) Test the sentiment analysis pipeline by inserting a new item directly into DynamoDB.
#    This simulates a feedback submission to see if the Lambda triggers and updates the item.
aws dynamodb put-item --table-name CustomerFeedbackAnalysis --region $AWS_REGION \
  --item '{
    "feedback_id": {"S": "pipeline-test-001"},
    "date": {"S": "2025-10-02T08:30:00Z"},
    "comment": {"S": "I really loved the service and support."},
    "customer_id": {"S": "pipeline-tester"},
    "status": {"S": "PENDING"}
  }'
# We've manually inserted a PENDING feedback item. This should trigger the DynamoDB stream.

# Wait a few seconds, then fetch the item to see if sentiment was added by the Lambda.
aws dynamodb get-item --table-name CustomerFeedbackAnalysis --region $AWS_REGION \
  --key '{
    "feedback_id": {"S": "pipeline-test-001"},
    "date": {"S": "2025-10-02T08:30:00Z"}
  }' \
  --consistent-read
# Check the output for attributes:
# - "sentiment": should be filled (e.g., "POSITIVE" or "NEGATIVE" etc.)
# - "sentimentScores": should contain the confidence scores.
# - "status": might have been updated to "PROCESSED".
# If these are present, the AnalyzeFeedbackSentiment function executed successfully on the stream event.

# 7.4 Also check CloudWatch Logs for the AnalyzeFeedbackSentiment function for any errors or confirmation.
aws logs tail /aws/lambda/AnalyzeFeedbackSentiment --since 1m --region $AWS_REGION
# This will stream logs from the past 1 minute. Look for any error messages or printouts from the Lambda (if the code logs the result).
# If you see logs indicating sentiment detection and updates, then the pipeline is working.

# -----------------------------
# Step 8: Amazon SNS for Email Alerts (Negative Feedback)
# -----------------------------
# The project includes an email alert feature for negative feedback using Amazon SNS (Simple Notification Service).
# We will set up an SNS topic and subscribe an email to it. The AnalyzeFeedbackSentiment Lambda will publish to this topic when a feedback is negative.

# 8.1 Create an SNS topic for alerts (e.g., "NegativeFeedbackAlerts").
export SNS_TOPIC_ARN=$(aws sns create-topic --name NegativeFeedbackAlerts --region $AWS_REGION --query "TopicArn" --output text)
echo "Created SNS Topic ARN: $SNS_TOPIC_ARN"
# The topic ARN will look like arn:aws:sns:<region>:<account-id>:NegativeFeedbackAlerts

# 8.2 Subscribe your email address to the SNS topic.
#    Replace the email address with the one that should receive alerts.
aws sns subscribe --topic-arn "$SNS_TOPIC_ARN" --protocol email \
  --notification-endpoint someone@example.com --region $AWS_REGION
# You will receive a subscription confirmation email at that address.

echo "Please check your email inbox for a message from AWS and confirm the SNS subscription."

# Wait for the user to confirm subscription before proceeding (the subscription must be confirmed to receive messages).
# (You can use `aws sns list-subscriptions-by-topic --topic-arn "$SNS_TOPIC_ARN"` to check if the subscription is confirmed. It will show "PendingConfirmation" until confirmed.)

# 8.3 Ensure the Lambda execution role has permission to publish to the SNS topic.
# We attached AmazonSNSFullAccess to the role earlier, which covers publishing to any SNS topic in the account.
# If using a more restrictive policy, ensure it allows `sns:Publish` to this topic ARN.

# 8.4 Update the AnalyzeFeedbackSentiment Lambda code to integrate SNS publishing.
# If not already implemented, modify analyze_feedback.py:
#  - Initialize an SNS client (boto3.client('sns')).
#  - After determining sentiment, if sentiment == "NEGATIVE", call sns.publish() to $SNS_TOPIC_ARN with a message.
# The message can include details like feedback_id, date, comment, sentiment for context.
#
# Pseudocode snippet for inside lambda_handler (for understanding):
#    if sentiment == "NEGATIVE":
#        sns_client.publish(
#           TopicArn = SNS_TOPIC_ARN,
#           Subject  = "Negative Feedback Alert",
#           Message  = f"Negative feedback received from {customer_id} on {date}: '{comment}' (Sentiment score: ...)"
#        )
#
# (In the actual code, ensure SNS_TOPIC_ARN is available - could pass it via environment variable or hardcode for simplicity.)
#
# If the provided analyze_feedback.py already contains SNS logic (as per project documentation), you may not need to change code. Just verify it's present.

# 8.5 Redeploy the updated AnalyzeFeedbackSentiment code to AWS.
zip analyze_feedback.zip analyze_feedback.py  # re-zip after code change (if any)
aws lambda update-function-code --function-name AnalyzeFeedbackSentiment \
  --zip-file fileb://analyze_feedback.zip --region $AWS_REGION

# 8.6 (Optional) Set the SNS topic ARN as an environment variable for the Lambda (if the code expects it).
aws lambda update-function-configuration --function-name AnalyzeFeedbackSentiment \
  --environment "Variables={SNS_TOPIC=$SNS_TOPIC_ARN}" --region $AWS_REGION
# Only do this if your analyze_feedback.py reads an environment variable for the topic ARN. Otherwise, skip.

# 8.7 Test the SNS integration.
# Manually invoke a negative feedback scenario to trigger an alert:
aws dynamodb put-item --table-name CustomerFeedbackAnalysis --region $AWS_REGION \
  --item '{
    "feedback_id": {"S": "alert-test-001"},
    "date": {"S": "2025-10-02T09:00:00Z"},
    "comment": {"S": "This is terrible, extremely disappointed."},
    "customer_id": {"S": "alert-tester"},
    "status": {"S": "PENDING"}
  }'
# This inserts a negative-sounding comment. The AnalyzeFeedbackSentiment Lambda should process it and detect sentiment as NEGATIVE, then publish to SNS.

# Wait a few moments for processing, then check your email for an alert notification from SNS.
# The email should contain the message published by the Lambda (with the feedback details).

# You can also verify via CLI if a message was published:
aws sns publish --topic-arn "$SNS_TOPIC_ARN" --subject "Test Alert" --message "Test alert from CLI" --region $AWS_REGION
# After running this, check the email to confirm you receive the "Test alert from CLI" message.
# (If not, make sure the subscription is confirmed and the email is correct.)

# -----------------------------
# Step 9: (Optional) Amazon Cognito for Admin Authentication
# -----------------------------
# **This step is optional** and only needed if you want to enforce login on the admin dashboard.
# Cognito will allow only authorized users to access the admin page and GET /feedback API.
# We'll outline the steps, but the admin dashboard code must support login for this to work.

# 9.1 Create a Cognito User Pool for admin users.
export COGNITO_POOL_ID=$(aws cognito-idp create-user-pool --pool-name FeedbackAdminPool --query "UserPool.Id" --output text --region $AWS_REGION)
echo "Created Cognito User Pool with ID: $COGNITO_POOL_ID"

# 9.2 Create a User Pool Client (application) for the web app to use Cognito.
export COGNITO_APP_CLIENT_ID=$(aws cognito-idp create-user-pool-client --user-pool-id $COGNITO_POOL_ID \
  --client-name FeedbackAppClient --no-generate-secret --query "UserPoolClient.ClientId" --output text --region $AWS_REGION)
echo "Created Cognito App Client with ID: $COGNITO_APP_CLIENT_ID"
# (We use --no-generate-secret because for a JavaScript web app, a client secret isn't used.)

# 9.3 Set up an admin user in the User Pool (you can also do this via the Cognito console for ease).
aws cognito-idp admin-create-user --user-pool-id $COGNITO_POOL_ID --username adminuser \
  --user-attributes Name=email,Value=adminuser@example.com Name=email_verified,Value=true \
  --temporary-password "TempPass123!" --message-action SUPPRESS --region $AWS_REGION
# This creates a user with a temporary password without sending an email (message_action SUPPRESS).
# Next, set a permanent password for the user:
aws cognito-idp admin-set-user-password --user-pool-id $COGNITO_POOL_ID --username adminuser \
  --password "SecurePass#2025" --permanent --region $AWS_REGION
# Credentials for admin login would be: Username: adminuser, Password: SecurePass#2025 (for example).

# 9.4 Update the API Gateway to secure GET /feedback with Cognito.
# Create a Cognito authorizer on the API Gateway that uses the new User Pool.
AUTH_ID=$(aws apigateway create-authorizer --rest-api-id $API_ID --name "FeedbackCognitoAuth" \
  --type COGNITO_USER_POOLS --provider-arns "arn:aws:cognito-idp:$AWS_REGION:$AWS_ACCOUNT_ID:userpool/$COGNITO_POOL_ID" \
  --identity-source 'method.request.header.Authorization' --query "id" --output text --region $AWS_REGION)
echo "Created Cognito Authorizer with ID: $AUTH_ID"

# Attach the authorizer to the GET method on /feedback.
aws apigateway update-method --rest-api-id $API_ID --resource-id $FEEDBACK_ID --http-method GET --region $AWS_REGION \
  --patch-operations "[{\"op\":\"replace\", \"path\":\"/authorizationType\", \"value\":\"COGNITO_USER_POOLS\"}, {\"op\":\"replace\", \"path\":\"/authorizerId\", \"value\":\"$AUTH_ID\"}]"
# Now the GET /feedback endpoint requires a valid Cognito JWT in the Authorization header.

# Redeploy API to apply changes.
aws apigateway create-deployment --rest-api-id $API_ID --stage-name dev --region $AWS_REGION

# 9.5 Update admin.html with Cognito configuration.
# In the admin page's JavaScript, configure the Cognito User Pool ID, App Client ID, and Region (and optionally, a domain for Hosted UI if using).
# Ensure the admin page code obtains a Cognito token (through user login) and includes it in the Authorization header for the GET request.
# This might involve using Amazon Cognito Identity JS SDK or AWS Amplify library in the admin page.
# (Detailed implementation is beyond this CLI guide; refer to AWS Cognito documentation or project docs.)
# After updating, upload admin.html to S3 again:
aws s3 cp frontend/admin.html s3://$BUCKET_NAME/admin.html --region $AWS_REGION

# With Cognito in place, the admin dashboard page will prompt for login (depending on your integration).
# Only after logging in will it retrieve data via GET /feedback successfully.

# -----------------------------
# Step 10: Verification & Usage
# -----------------------------
# At this point, the system should be fully set up. Let's recap and verify each component:

# 10.1 **Frontend Web App**: 
#    - URL: $website_url (S3 static website endpoint).
#    - Try accessing the URL in your browser. You should see the feedback submission form (index.html).
#    - If you try to submit feedback through the form, it will call the POST API and you should see a success message if everything is configured properly.

# 10.2 **Submit a Feedback (End-to-End Test)**:
#    Go to the website or use curl to submit a new feedback. For example:
curl -X POST -H "Content-Type: application/json" \
  -d '{"customer_id": "cust001", "comment": "Absolutely loved the service!", "date": "2025-10-02T10:00:00Z"}' \
  $API_URL
# Expected result: The API should respond with a success (HTTP 200). The feedback is stored in DynamoDB, and the Analyze lambda will soon process it.

# 10.3 **Check DynamoDB for Processing**:
#    After a few seconds, query the DynamoDB table for the new item to see if it has been processed:
aws dynamodb scan --table-name CustomerFeedbackAnalysis --region $AWS_REGION \
  --projection-expression "feedback_id, comment, status, sentiment, sentimentScores"
# Find the entry for cust001 or the comment "Absolutely loved...".
# Verify:
#  - status is "PROCESSED"
#  - sentiment is "POSITIVE" (likely, given the comment) or other correct sentiment
#  - sentimentScores are present (the JSON with scores).
# This confirms that the sentiment analysis was performed and the item was updated with results.

# 10.4 **Admin Dashboard**:
#    Navigate to $website_url/admin.html in your browser.
#    - If Cognito is not enforced (authorizationType NONE), the page should load the data immediately.
#    - If Cognito is enabled, log in with your admin credentials, and then the page will list all feedback entries.
#    You should see the feedback entries table with their sentiments and statuses. Try using the filter or export features (if implemented in the project).
#    Also note the color-coding and charts (if present in this version of admin.html).

# 10.5 **Negative Feedback Alert**:
#    Submit a feedback with a clearly negative sentiment (either via the form or curl):
curl -X POST -H "Content-Type: application/json" \
  -d '{"customer_id": "cust002", "comment": "This was the worst experience ever.", "date": "2025-10-02T10:05:00Z"}' \
  $API_URL
# After it's processed (give it a little time), the AnalyzeFeedbackSentiment Lambda should send an SNS email alert.
# Check the subscribed email inbox for a notification about the negative feedback.

# 10.6 **CloudWatch Logs**:
#    You can monitor logs for each Lambda to debug issues:
#    SubmitFeedbackFunction logs: /aws/lambda/SubmitFeedbackFunction
#    GetFeedbackFunction logs:    /aws/lambda/GetFeedbackFunction
#    AnalyzeFeedbackSentiment logs: /aws/lambda/AnalyzeFeedbackSentiment
#    Example: tail logs for AnalyzeFeedbackSentiment (last 5 minutes):
aws logs tail /aws/lambda/AnalyzeFeedbackSentiment --since 5m --region $AWS_REGION --format short

# If everything is working, you've successfully deployed the project! 🎉

# -----------------------------
# Troubleshooting & Common Issues
# -----------------------------
# If you encounter problems, here are some common issues and how to resolve them:

# - **AWS CLI not found**: If `aws` commands are not recognized, ensure AWS CLI is installed and in your PATH. On Mac, you might need to restart your terminal or run `source ~/.bash_profile` if AWS CLI was just installed.

# - **"Access Denied" or permissions errors**: Double-check that the IAM role (LambdaFeedbackRole) has all required policies attached. If a Lambda can't perform an action (e.g., DynamoDB write or SNS publish), it will log an error. Attach the necessary policy and update the function's role if missed. Also ensure the AWS user running the CLI has rights to create resources.

# - **Bucket already exists / naming errors**: S3 bucket names must be globally unique. If `aws s3 mb` fails with a naming conflict, choose a different bucket name (modify BUCKET_NAME with a more unique string and retry). If website URL is not accessible, ensure you disabled public access block and set the bucket policy correctly.

# - **API Gateway errors (HTTP 403 or 502)**: 
#   * 403 Forbidden from API calls might indicate missing permissions for API Gateway to invoke Lambda (re-check the lambda add-permission commands). 
#   * 502 Bad Gateway from API means Lambda invocation failed. Check CloudWatch logs for the Lambda function to see the error. 
#   * If CORS issues occur (visible in browser console), ensure the OPTIONS method and CORS headers are properly set as in Step 5.8, and that the API was redeployed after making those changes.

# - **DynamoDB Stream not triggering Lambda**: Ensure you enabled the stream on the DynamoDB table and created the event source mapping. Verify the mapping state is Enabled. If the Lambda isn't firing, check CloudWatch logs for any errors, and ensure the Lambda's role has proper permissions (it should, given DynamoDBFullAccess).

# - **No sentiment or status not updating**: This means the AnalyzeFeedbackSentiment Lambda didn't complete successfully. Check its CloudWatch logs for errors (e.g., missing TABLE_NAME env variable, or text too short/long for Comprehend). Also verify Comprehend is available in your region (the `aws comprehend detect-sentiment` test in step 10 architecture verification can be tried manually to ensure Comprehend works in chosen region).

# - **SNS email not received**: Ensure the subscription is confirmed (use `aws sns list-subscriptions-by-topic --topic-arn "$SNS_TOPIC_ARN"` to check; it should show a SubscriptionArn (no "Pending")). Also check the Lambda logs to see if a publish was attempted or if any error occurred (e.g., topic ARN incorrect or permissions issue).

# - **Cognito login issues** (if implemented): If using Cognito and unable to login on admin.html, ensure the user exists and the credentials are correct. Check the browser console for any errors from the Cognito SDK. You might need to integrate Amplify or AWS Cognito SDK properly in the admin page. If the GET API returns 401 Unauthorized, verify the token is being included in the request and that the API Gateway authorizer is configured with the correct User Pool. You can temporarily remove the authorizer (set auth to NONE) to test the flow without Cognito.

# - **Cleaning up**: If you are done testing, remember to remove resources to avoid incurring costs:
#   Use AWS CLI or console to delete the S3 bucket (and contents), DynamoDB table, Lambdas, API Gateway, Cognito pool (if created), and SNS topic/subscription.
#   For example: `aws s3 rb s3://$BUCKET_NAME --force` to delete bucket, `aws dynamodb delete-table --table-name CustomerFeedbackAnalysis`, etc.

# End of script.
