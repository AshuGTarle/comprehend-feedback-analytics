<!-- Step 1.1: Verified bucket creation using 'aws s3 ls' and checked region -->
<!-- Step 2: Created DynamoDB table (CustomerFeedbackAnalysis) with feedback_id + date keys -->
<!-- Step 3: Created IAM Role (LambdaFeedbackRole) with policies for S3, DynamoDB, Comprehend, CloudWatch -->
- ⏳ Step 4: Next — Create Lambda function for feedback submission
- ✅ Step 4: Created Lambda function (SubmitFeedbackFunction) from submit_feedback.py
- ✅ Step 4.4: Tested SubmitFeedbackFunction with sample event (test-feedback.json)
- ✅ Step 4.5: Verified feedback record was saved in DynamoDB (CustomerFeedbackAnalysis)
- ⏳ Step 5.1: Created API Gateway (FeedbackAPI)
- ⏳ Step 5.2: Created /feedback resource in API Gateway
- ⏳ Step 5.3: Added POST method to /feedback and linked it with SubmitFeedbackFunction
- ✅ Step 5.4: Deployed API to 'dev' stage → accessible at:
  https://e8oqjp3ji4.execute-api.eu-central-1.amazonaws.com/dev/feedback
- ✅ Step 6: Connected frontend (index.html) to API Gateway endpoint
- ⏳ Hosting options: S3 Static Website or AWS Amplify
- ✅ Step 6.1: Uploaded index.html to S3 bucket and enabled static website hosting
- ✅ Step 6.2: Allowed public access by disabling block policy and adding bucket policy
- ✅ Website available at: http://customer-feedback-data-ashutosh.s3-website.eu-central-1.amazonaws.com

- ✅ Step 7: Configured CORS for API Gateway
  - Added OPTIONS method with MOCK integration
  - Declared Access-Control-Allow headers in method response
  - Attached integration response with CORS headers
  - Redeployed API

- ✅ Step 8: Verified End-to-End Functionality
  - Tested POST request with curl → feedback stored in DynamoDB
  - Verified DynamoDB record exists
  - Tested OPTIONS request → confirmed CORS headers returned

- ✅ Step 9: Polished frontend (index.html)
  - Added clean UI with card layout, shadows, and hover effects
  - Enhanced form styling for inputs, textarea, and button
  - Status messages styled with green (success) and red (error)
  - Mobile responsive for smaller screens
  - Uploaded updated index.html to S3 bucket


### ✅ Step 10: Amazon Comprehend connected (real sentiment)

- Gave the Lambda execution role permissions:
  - `AWSLambdaBasicExecutionRole` (logs)
  - `ComprehendFullAccess` (sentiment API)
- Verified service activation in **eu-central-1**:
  ```bash
  aws comprehend detect-sentiment --text 'I love this product!' --language-code en --region eu-central-1




## Step 11: Add CloudFront for HTTPS Frontend

# Create CloudFront distribution for S3 bucket
aws cloudfront create-distribution \
  --origin-domain-name customer-feedback-data-ashutosh.s3.eu-central-1.amazonaws.com \
  --default-root-object index.html

# Note the "DomainName" from output (e.g., d3f9example.cloudfront.net)

# New HTTPS link will be:
# https://<CloudFrontDomainName>/


- ✅ Step 12: Added Admin Dashboard to view all feedback
  - Created GetFeedbackFunction Lambda to read DynamoDB items
  - Added GET /feedback method in API Gateway linked to GetFeedbackFunction
  - Granted API Gateway permission to invoke Lambda
  - Redeployed API (now supports both POST and GET on /feedback)
  - Created admin.html page with a styled table showing all feedback
  - Uploaded admin.html to S3 bucket
  - Accessible at:
    http://customer-feedback-data-ashutosh.s3-website.eu-central-1.amazonaws.com/admin.html




### Step 13: Sentiment Analysis with Amazon Comprehend

In this step, we integrate Amazon Comprehend with our feedback system.  
We create a Lambda function `AnalyzeFeedbackSentiment` that:

- Is triggered whenever a new feedback item is inserted into the DynamoDB table via **DynamoDB Streams**.  
- Sends the feedback text to **Amazon Comprehend** for sentiment analysis.  
- Updates the same record in DynamoDB with the detected sentiment (`Positive`, `Negative`, `Neutral`, or `Mixed`) and sentiment scores.

#### Commands:
```bash
cd lambda
zip analyze_feedback.zip analyze_feedback.py

aws lambda create-function \
  --function-name AnalyzeFeedbackSentiment \
  --runtime python3.12 \
  --role arn:aws:iam::031857855750:role/LambdaDynamoDBComprehendRole \
  --handler analyze_feedback.lambda_handler \
  --zip-file fileb://analyze_feedback.zip \
  --region eu-central-1

aws lambda create-event-source-mapping \
  --function-name AnalyzeFeedbackSentiment \
  --event-source arn:aws:dynamodb:eu-central-1:031857855750:table/CustomerFeedbackAnalysis/stream/2025-09-30T21:10:53.331 \
  --batch-size 1 \
  --starting-position LATEST \
  --region eu-central-1

aws lambda list-event-source-mappings \
  --function-name AnalyzeFeedbackSentiment \
  --region eu-central-1



### Step 14: Testing the Sentiment Analysis Pipeline

After deploying the Lambda and connecting it to DynamoDB Streams, we can test the full pipeline.

1. Insert feedback into DynamoDB:
```bash
aws dynamodb put-item \
  --table-name CustomerFeedbackAnalysis \
  --item '{
    "feedback_id": {"S": "pipeline-test-positive"},
    "date": {"S": "2025-10-01T13:00:00Z"},
    "feedbackText": {"S": "I really loved the service and product quality!"}
  }' \
  --region eu-central-1


Retrieve the item to confirm that Amazon Comprehend added sentiment results:

aws dynamodb get-item \
  --table-name CustomerFeedbackAnalysis \
  --key '{"feedback_id": {"S": "pipeline-test-positive"}, "date": {"S": "2025-10-01T13:00:00Z"}}' \
  --region eu-central-1


✅ Expected output:

{
  "feedback_id": "pipeline-test-positive",
  "date": "2025-10-01T13:00:00Z",
  "feedbackText": "I really loved the service and product quality!",
  "sentiment": "POSITIVE",
  "sentimentScores": "{...}"
}


Check CloudWatch logs for detailed Lambda execution:

aws logs tail /aws/lambda/AnalyzeFeedbackSentiment --follow --region eu-central-1



### Step 15: Mark Feedback as PROCESSED After Sentiment Analysis

Previously, the AnalyzeFeedbackSentiment Lambda only added sentiment results
(`sentiment`, `sentimentScores`) to DynamoDB but left the `status` as `PENDING`.
This caused the Admin Dashboard to always display "PENDING".

We fixed this by updating `analyze_feedback.py` so it also sets:

```json
"status": "PROCESSED"
Deployment
Modify analyze_feedback.py with the new update expression:

python
Copy code
table.update_item(
    Key={
        'feedback_id': feedback_id,
        'date': date
    },
    UpdateExpression="SET sentiment = :s, sentimentScores = :sc, #st = :st",
    ExpressionAttributeNames={
        "#st": "status"
    },
    ExpressionAttributeValues={
        ':s': sentiment,
        ':sc': json.dumps(sentiment_scores),
        ':st': "PROCESSED"
    }
)
Re-zip and redeploy the Lambda:

bash
Copy code
cd lambda
zip analyze_feedback.zip analyze_feedback.py

aws lambda update-function-code \
  --function-name AnalyzeFeedbackSentiment \
  --zip-file fileb://analyze_feedback.zip \
  --region eu-central-1
Submit a new feedback through the frontend.

Expected Result
New feedback → status starts as PENDING

After a few seconds (once Comprehend runs) → DynamoDB item updated with:

sentiment

sentimentScores

status = PROCESSED

Admin Dashboard now shows PROCESSED instead of being stuck at PENDING.

Copy code




### Step 15: Fix Sentiment Analysis Lambda (AnalyzeFeedbackSentiment)

We encountered an issue where some DynamoDB items had **`comment`** while others had **`feedbackText`**.  
This caused our `AnalyzeFeedbackSentiment` Lambda to crash with `KeyError: 'feedbackText'`.

#### ✅ Solution
- Updated `analyze_feedback.py` to handle both keys (`feedbackText` and `comment`).  
- Added safe checks so invalid records are skipped gracefully.  
- Ensured DynamoDB is updated with:
  - `sentiment`
  - `sentimentScores`
  - `status = PROCESSED`

#### 🔧 Update Process
1. Edited `lambda/analyze_feedback.py` with the new code.  
2. Zipped and deployed the update:

```bash
cd lambda
zip analyze_feedback.zip analyze_feedback.py
aws lambda update-function-code \
  --function-name AnalyzeFeedbackSentiment \
  --zip-file fileb://analyze_feedback.zip \
  --region eu-central-1
Verified update with:

bash
Copy code
aws lambda get-function --function-name AnalyzeFeedbackSentiment --region eu-central-1
Tested by inserting a new DynamoDB record and confirmed it was processed:

bash
Copy code
aws dynamodb put-item \
  --table-name CustomerFeedbackAnalysis \
  --item '{
    "feedback_id": {"S": "test-fix-001"},
    "date": {"S": "2025-10-01T12:34:00Z"},
    "comment": {"S": "This fix should work now!"}
  }' \
  --region eu-central-1
Checked CloudWatch logs and confirmed the Lambda processes both comment and feedbackText without error.



## Step 17: Deploying Sentiment Analysis Pipeline

We updated the **AnalyzeFeedbackSentiment Lambda** to normalize fields and ensure consistency between
`submit_feedback` and `analyze_feedback`.

### Changes:
- DynamoDB records now always use `comment` (instead of sometimes `feedbackText`).
- `AnalyzeFeedbackSentiment` Lambda updates:
  - `status` → changes from **PENDING** to **PROCESSED** after analysis.
  - `sentiment` → one of POSITIVE, NEGATIVE, NEUTRAL, MIXED.
  - `sentimentScores` → JSON with score distribution from AWS Comprehend.

### How it works:
1. User submits feedback → DynamoDB entry with status **PENDING**.
2. DynamoDB Streams trigger **AnalyzeFeedbackSentiment Lambda**.
3. Lambda calls AWS Comprehend to analyze sentiment.
4. DynamoDB entry updated with:
   - `status = PROCESSED`
   - `sentiment`
   - `sentimentScores`
5. Admin dashboard fetches and displays updated data.

### Example DynamoDB Item
```json
{
  "feedback_id": "test-fix-001",
  "date": "2025-10-01T12:34:00Z",
  "customer_id": "123",
  "comment": "This fix should work now!",
  "status": "PROCESSED",
  "sentiment": "NEGATIVE",
  "sentimentScores": {
    "Positive": 0.07,
    "Negative": 0.69,
    "Neutral": 0.03,
    "Mixed": 0.19
  }
}


## Step 17: Admin Dashboard with Sentiment Scores

We enhanced the **Admin Dashboard (`admin.html`)** to also display **sentiment analysis scores** from Amazon Comprehend.  

### Deployment
Upload the updated `admin.html` file to S3:

```bash
aws s3 cp frontend/admin.html s3://customer-feedback-data-ashutosh/ --region eu-central-1



## Step 18: Sentiment Scores as Percentages

We improved the **Admin Dashboard (`admin.html`)** to make sentiment analysis results more readable.

### What Changed
- The **Scores** column now shows sentiment breakdowns (Positive, Negative, Neutral, Mixed) as **percentages**.
- Example:
  - Positive: 85.2%
  - Negative: 3.1%
  - Neutral: 11.2%
  - Mixed: 0.5%

### Deployment
Upload the updated `admin.html` file to your S3 bucket:

```bash
aws s3 cp frontend/admin.html s3://customer-feedback-data-ashutosh/ --region eu-central-1



## Step 19: Color-coded Sentiment in Admin Dashboard

We enhanced the **Admin Dashboard (`admin.html`)** to make sentiment results more user-friendly by adding **color-coded labels**.

### What Changed
- **POSITIVE** → Green  
- **NEGATIVE** → Red  
- **NEUTRAL** → Gray  
- **MIXED** → Orange  

This allows quick visual scanning of customer sentiment without reading numbers.

### Deployment
Upload the updated `admin.html` file to your S3 bucket:

```bash
aws s3 cp frontend/admin.html s3://customer-feedback-data-ashutosh/ --region eu-central-1



### Step 18: Enhanced Admin Dashboard (Filters + Sentiment Scores)

We improved the **Admin Dashboard** (`admin.html`) to make it more functional:

- Added **filters**:
  - Status filter (All / Pending / Processed)
  - Sentiment filter (All / Positive / Negative / Neutral / Mixed)
- Sorted results by **newest first** (date-based sorting).
- Displayed **sentiment scores** (Positive, Negative, Neutral, Mixed as percentages).
- Applied **color coding**:
  - Green = Positive
  - Red = Negative
  - Gray = Neutral
  - Orange = Mixed
- Wrapped logic in a **`DOMContentLoaded` listener** so scripts run only after the DOM is ready, preventing errors.

#### Deploy Updated Admin Page
```bash
aws s3 cp frontend/admin.html s3://customer-feedback-data-ashutosh/ --region eu-central-1





---

### 📌 `README.md`

```markdown
## Step 15: Admin Dashboard with Charts

The Admin Dashboard (`admin.html`) now includes **visual analytics** alongside the feedback table.

### Features Added:
- **Sentiment Distribution Pie Chart** → shows share of Positive, Negative, Neutral, and Mixed feedback.
- **Status Overview Bar Chart** → shows counts of Pending vs Processed feedback.
- **Feedback Over Time Line Chart** → shows number of feedback entries per day.

### Tech Used:
- [Chart.js](https://www.chartjs.org/) for rendering interactive charts.
- CSS grid layout to arrange charts (Pie + Bar side by side, Line below).
- Charts refresh automatically when filters are applied.

### Deployment:
```bash
aws s3 cp frontend/admin.html s3://customer-feedback-data-ashutosh/admin.html --region eu-central-1



### Step 20: SNS Email Alerts for Negative Feedback

To make sure critical customer issues don’t get missed, we set up **Amazon SNS (Simple Notification Service)** to send an **email alert** whenever negative feedback is detected.

#### Setup:
1. Create an SNS Topic:
   ```bash
   aws sns create-topic \
     --name NegativeFeedbackAlerts \
     --region eu-central-1
Subscribe your email address:

bash
Copy code
aws sns subscribe \
  --topic-arn arn:aws:sns:eu-central-1:031857855750:NegativeFeedbackAlerts \
  --protocol email \
  --notification-endpoint tarleashutosh@gmail.com \
  --region eu-central-1


  ### Step 22: Export Feedback to CSV

We enhanced the Admin Dashboard with an **Export CSV** feature.  
Admins can now download all feedback data (including sentiment analysis results) as a CSV file for offline analysis.

#### Changes Made:
- Added an **Export CSV** button beside filters.
- Implemented `exportCSV()` in JavaScript:
  - Takes the current dataset (`globalData`).
  - Converts it into a CSV format.
  - Triggers a file download named `feedback_export.csv`.

#### Usage:
1. Open the Admin Dashboard:







# Customer Feedback Analytics Platform

This project is a full-stack AWS-based feedback collection and sentiment analysis system.

---

## Features
- **Frontend (S3 + CloudFront)**:
  - `index.html` → Public customer feedback submission form (no login required).
  - `admin.html` → Cognito-protected dashboard with charts and analytics.
- **Backend**:
  - API Gateway + Lambda + DynamoDB.
  - AWS Comprehend for sentiment analysis.
- **Authentication**:
  - Cognito required only for `admin.html` (dashboard).
  - Public `index.html` for customer feedback.

---

## Deployment Steps

### 1. Upload Frontend
```bash
# Upload public feedback form
aws s3 cp ../frontend/index.html s3://customer-feedback-data-ashutosh/index.html --region eu-central-1

# Upload admin dashboard (requires Cognito login)
aws s3 cp ../frontend/admin.html s3://customer-feedback-data-ashutosh/admin.html --region eu-central-1
2. Invalidate CloudFront Cache
bash
Copy code
aws cloudfront create-invalidation \
  --distribution-id E2RNG6S13K3K4B \
  --paths "/index.html" "/admin.html"
3. Test API Gateway
bash
Copy code
aws apigateway test-invoke-method \
  --rest-api-id e8oqjp3ji4 \
  --resource-id lv65kp \
  --http-method POST \
  --path-with-query-string "/feedback" \
  --body '{
    "feedback_id": "fb1002",
    "date": "2025-10-02T10:00:00Z",
    "customer_id": "cust-test",
    "comment": "Public feedback test",
    "status": "PENDING"
  }' \
  --region eu-central-1
Notes
Feedback Form (index.html): Open for public customers. No Cognito required.

Admin Dashboard (admin.html): Secure, requires Cognito login.

DynamoDB: Stores feedback with sentiment analysis results from AWS Comprehend.

Architecture
Frontend → S3 + CloudFront

API Layer → API Gateway (with CORS enabled)

Business Logic → Lambda Functions (submit, process, get feedback)

Database → DynamoDB (with Streams for processing)

AI/ML → AWS Comprehend (sentiment analysis)

Authentication → Cognito (for admin dashboard only)

pgsql
Copy code

---

👉 With this update, your repo now shows **clear separation**:  
- Public feedback form = `index.html`  
- Admin dashboard (Cognito) = `admin.html`  

Do you also want me to add a **diagram (architecture flow in README)** so recruiters/managers immediately see the full pipeline?




