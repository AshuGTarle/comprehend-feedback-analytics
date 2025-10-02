import boto3
import json
import os
from decimal import Decimal

# Initialize AWS clients
comprehend = boto3.client('comprehend', region_name='eu-central-1')
dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
sns = boto3.client('sns', region_name='eu-central-1')

# Env vars
table_name = os.environ['TABLE_NAME']
sns_topic_arn = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:eu-central-1:031857855750:NegativeFeedbackAlerts')

table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    for record in event['Records']:
        if record['eventName'] == 'INSERT':
            new_image = record['dynamodb']['NewImage']

            # Handle both "feedbackText" and "comment"
            if 'feedbackText' in new_image:
                feedback_text = new_image['feedbackText']['S']
            elif 'comment' in new_image:
                feedback_text = new_image['comment']['S']
            else:
                print("No feedback text found, skipping")
                continue

            feedback_id = new_image['feedback_id']['S']
            date = new_image['date']['S']
            customer_id = new_image.get('customer_id', {}).get('S', 'Unknown')

            # Call Comprehend
            response = comprehend.detect_sentiment(
                Text=feedback_text,
                LanguageCode='en'
            )

            sentiment = response['Sentiment']
            sentiment_scores = response['SentimentScore']

            # Convert floats → Decimal for DynamoDB
            sentiment_scores_decimal = {k: Decimal(str(v)) for k, v in sentiment_scores.items()}

            # Update DynamoDB with sentiment + mark as PROCESSED
            table.update_item(
                Key={
                    'feedback_id': feedback_id,
                    'date': date
                },
                UpdateExpression="set sentiment = :s, sentimentScores = :sc, #st = :st",
                ExpressionAttributeNames={
                    '#st': 'status'
                },
                ExpressionAttributeValues={
                    ':s': sentiment,
                    ':sc': sentiment_scores_decimal,
                    ':st': 'PROCESSED'
                }
            )

            # 🚨 If sentiment is NEGATIVE → send SNS alert
            if sentiment == "NEGATIVE":
                message = (
                    f"🚨 Negative Feedback Alert 🚨\n\n"
                    f"Customer ID: {customer_id}\n"
                    f"Date: {date}\n"
                    f"Feedback: {feedback_text}\n"
                    f"Sentiment: {sentiment}\n"
                )
                sns.publish(
                    TopicArn=sns_topic_arn,
                    Subject="Negative Feedback Alert",
                    Message=message
                )
                print(f"Alert sent to SNS for feedback_id {feedback_id}")

    return {"status": "done"}
