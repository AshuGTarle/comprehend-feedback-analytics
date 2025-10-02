import boto3
import json
import uuid
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('CustomerFeedbackAnalysis')

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        
        # Handle both payload formats (frontend form and test tools)
        customer_id = body.get('customer_id', 'unknown')
        feedback_text = body.get('comment') or body.get('feedbackText', '')

        feedback_id = str(uuid.uuid4())
        date = datetime.utcnow().isoformat() + "Z"

        # Insert into DynamoDB
        table.put_item(
            Item={
                'feedback_id': feedback_id,
                'date': date,
                'customer_id': customer_id,
                'feedbackText': feedback_text,
                'status': 'PENDING'
            }
        )

        # Success response
        return {
            'statusCode': 200,
            'headers': {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            'body': json.dumps({
                "message": "Feedback submitted",
                "feedback_id": feedback_id,
                "date": date
            })
        }
    except Exception as e:
        # Error response with CORS headers too
        return {
            'statusCode': 500,
            'headers': {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            'body': json.dumps({
                "error": str(e),
                "message": "Failed to submit feedback"
            })
        }
