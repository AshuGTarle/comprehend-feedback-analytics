import boto3
import os
import json

# Initialize DynamoDB
ddb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('DDB_TABLE', 'CustomerFeedbackAnalysis')
table = ddb.Table(TABLE_NAME)

def lambda_handler(event, context):
    # Scan the table (all feedback items)
    response = table.scan()
    items = response.get('Items', [])

    # Normalize field names for frontend
    normalized = []
    for item in items:
        # Parse sentiment scores safely
        sentiment_scores = {}
        if 'sentimentScores' in item:
            try:
                sentiment_scores = json.loads(item['sentimentScores'])
            except Exception:
                sentiment_scores = item['sentimentScores']  # fallback to raw string if already parsed

        normalized.append({
            'feedback_id': item.get('feedback_id'),
            'date': item.get('date'),
            'customer_id': item.get('customer_id', ''),
            'comment': item.get('feedbackText', item.get('comment', '')),  # support both field names
            'status': item.get('status', 'PENDING'),
            'sentiment': item.get('sentiment', 'Analyzing...'),
            'sentimentScores': sentiment_scores  # include scores for dashboard
        })

    # Return JSON response
    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",   # CORS support
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        'body': json.dumps(normalized, default=str)
    }
