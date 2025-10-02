import boto3
import os
import json

ddb = boto3.resource('dynamodb')
comprehend = boto3.client('comprehend')

TABLE_NAME = os.environ.get('DDB_TABLE', 'CustomerFeedbackAnalysis')
table = ddb.Table(TABLE_NAME)

def lambda_handler(event, context):
    for record in event.get('Records', []):
        if record.get('eventName') not in ('INSERT', 'MODIFY'):
            continue

        new_image = record.get('dynamodb', {}).get('NewImage', {})
        if not new_image:
            continue

        status = new_image.get('status', {}).get('S', '')
        if status != 'PENDING':
            continue

        feedback_id = new_image['feedback_id']['S']
        date = new_image['date']['S']
        comment = new_image.get('comment', {}).get('S', '')
        if not comment:
            continue

        # --- Amazon Comprehend ---
        resp = comprehend.detect_sentiment(Text=comment, LanguageCode='en')
        sentiment = resp['Sentiment']
        score = resp['SentimentScore']

        # Update the item in DynamoDB
        table.update_item(
            Key={'feedback_id': feedback_id, 'date': date},
            UpdateExpression="""
                SET sentiment = :s,
                    sentiment_score = :sc,
                    #st = :p
            """,
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':s': sentiment,
                ':sc': {
                    'Positive': score['Positive'],
                    'Negative': score['Negative'],
                    'Neutral':  score['Neutral'],
                    'Mixed':    score['Mixed']
                },
                ':p': 'PROCESSED'
            }
        )

    return {'statusCode': 200, 'body': json.dumps({'ok': True})}
