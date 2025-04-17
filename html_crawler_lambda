import json
import logging
import os
import re
from urllib.parse import urlparse

# Using standard library for HTTP requests for simplicity in Lambda
# If complex headers/retries are needed, package 'requests' library instead
import urllib.request
import urllib.error

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients (outside handler for potential reuse)
s3_client = boto3.client("s3")
sqs_client = boto3.client("sqs")

# --- Configuration ---
# Get S3 bucket name and SQS queue URL from environment variables
# ** IMPORTANT: Set these environment variables in your Lambda function config **
RAW_HTML_S3_BUCKET = os.environ.get("RAW_HTML_S3_BUCKET")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL") # Needed for deleting messages

if not RAW_HTML_S3_BUCKET:
    logger.critical("Environment variable RAW_HTML_S3_BUCKET is not set.")
    # raise ValueError("Environment variable RAW_HTML_S3_BUCKET is not set.")
if not SQS_QUEUE_URL:
    logger.critical("Environment variable SQS_QUEUE_URL is not set.")
    # raise ValueError("Environment variable SQS_QUEUE_URL is not set.")


def fetch_html(url):
    """Fetches HTML content from a given URL."""
    logger.info(f"Attempting to fetch HTML from: {url}")
    try:
        # Add a user-agent header to avoid potential blocking
        headers = {
            "User-Agent": "AWS Lambda Crawler Bot (https://aws.amazon.com/lambda/)"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:  # 20s timeout
            if response.status == 200:
                # Check content type - basic check for HTML
                content_type = response.headers.get("Content-Type", "").lower()
                if "html" in content_type:
                    logger.info(
                        f"Successfully fetched HTML (Status: 200, Content-Type: {content_type})"
                    )
                    # Read and decode, handling potential encoding issues
                    # Use 'replace' to avoid crashing on bad characters
                    return response.read().decode(
                        response.headers.get_content_charset("utf-8"),
                        errors="replace",
                    )
                else:
                    logger.warning(
                        f"Skipping URL {url}. Content-Type is not HTML: {content_type}"
                    )
                    return None # Treat non-HTML as a skippable "failure" for this purpose
            else:
                logger.error(
                    f"Failed to fetch URL {url}. Status code: {response.status}"
                )
                return None
    except urllib.error.HTTPError as e:
        # Specific HTTP errors (like 404 Not Found, 403 Forbidden)
        logger.error(f"HTTP Error fetching URL {url}: {e.code} {e.reason}")
        return None
    except urllib.error.URLError as e:
        # Other URL errors (like network connection issues, invalid domain)
        logger.error(f"URL Error fetching URL {url}: {e.reason}")
        return None
    except Exception as e:
        # Catch-all for unexpected errors (timeouts, etc.)
        logger.error(f"An unexpected error occurred fetching {url}: {e}")
        return None


def sanitize_url_to_s3_key(url):
    """Creates a safe S3 key from a URL."""
    try:
        parsed_url = urlparse(url)
        # Start with netloc (domain) and path
        key = parsed_url.netloc + parsed_url.path

        # Remove leading/trailing slashes if they exist
        key = key.strip("/")

        # Replace common problematic characters with underscores
        key = re.sub(r'[\\?&=#%:]', '_', key)
        # Replace multiple consecutive slashes/underscores with a single one
        key = re.sub(r'[/_]+', '_', key)

        # Add .html extension if not present (optional, but good practice)
        if not key.lower().endswith((".html", ".htm")):
             key += ".html"

        # S3 key length limit is 1024 bytes. Truncate if necessary (rare).
        max_len = 1000 # Leave some buffer
        if len(key.encode('utf-8')) > max_len:
            # Simple truncation - more sophisticated methods exist if needed
            key = key[:max_len]
            # Ensure it doesn't end mid-character in multi-byte encodings (basic check)
            while len(key.encode('utf-8')) > max_len:
                key = key[:-1]
            logger.warning(f"Sanitized key for {url} was truncated due to length.")

        # Handle edge case of empty key after sanitization
        if not key or key == ".html":
            key = f"default_{hash(url)}.html" # Fallback key

        logger.info(f"Sanitized URL '{url}' to S3 key: '{key}'")
        return key
    except Exception as e:
        logger.error(f"Error sanitizing URL {url}: {e}")
        # Fallback key if sanitization fails completely
        return f"error_sanitizing_{hash(url)}.html"


def save_to_s3(bucket, key, content):
    """Saves content to an S3 object."""
    logger.info(f"Saving content to s3://{bucket}/{key}")
    try:
        response = s3_client.put_object(
            Bucket=bucket, Key=key, Body=content, ContentType="text/html"
        )
        logger.info(f"Successfully saved to S3. ETag: {response.get('ETag')}")
        return True
    except Exception as e:
        logger.error(f"Failed to save to S3 bucket {bucket}, key {key}: {e}")
        return False


def delete_sqs_message(queue_url, receipt_handle):
    """Deletes a message from the SQS queue."""
    logger.info(f"Attempting to delete message with handle: {receipt_handle[:10]}...") # Log partial handle
    try:
        sqs_client.delete_message(
            QueueUrl=queue_url, ReceiptHandle=receipt_handle
        )
        logger.info("Successfully deleted message from SQS.")
        return True
    except Exception as e:
        # Log error but don't raise, as the main goal was achieved (S3 upload)
        # The message will eventually expire or be retried.
        logger.error(f"Failed to delete message from SQS ({queue_url}): {e}")
        return False


def lambda_handler(event, context):
    """
    Lambda handler function triggered by SQS.
    Processes messages containing URLs, fetches HTML, saves to S3.
    """
    logger.info(f"Received {len(event.get('Records', []))} SQS message(s).")

    if not RAW_HTML_S3_BUCKET or not SQS_QUEUE_URL:
        logger.error("Missing required environment variables. Aborting.")
        # You might want to return an error structure if the trigger expects it
        # For SQS, failing here might cause the whole batch to retry.
        return {"batchItemFailures": [{"itemIdentifier": record.get('messageId')} for record in event.get('Records', [])]}


    processed_successfully = 0
    failed_processing = 0
    batch_item_failures = [] # For reporting partial batch failures back to SQS

    for record in event.get("Records", []):
        message_id = record.get("messageId")
        receipt_handle = record.get("receiptHandle")
        url = record.get("body") # Assuming the URL is the message body

        if not url or not receipt_handle:
            logger.warning(f"Skipping record: Missing URL or receipt handle. ID: {message_id}")
            # Report failure for this specific item if possible
            if message_id:
                 batch_item_failures.append({"itemIdentifier": message_id})
            failed_processing += 1
            continue

        logger.info(f"Processing URL: {url} (Message ID: {message_id})")

        # 1. Fetch HTML
        html_content = fetch_html(url)

        if html_content is not None:
            # 2. Sanitize URL for S3 Key
            s3_key = sanitize_url_to_s3_key(url)

            # 3. Save to S3
            s3_success = save_to_s3(RAW_HTML_S3_BUCKET, s3_key, html_content)

            if s3_success:
                # 4. Delete SQS Message ONLY if S3 upload was successful
                delete_success = delete_sqs_message(SQS_QUEUE_URL, receipt_handle)
                if delete_success:
                    processed_successfully += 1
                else:
                    # S3 succeeded, but delete failed. Logged in delete_sqs_message.
                    # Don't mark as batch failure, S3 write was the critical part.
                    # Message will likely expire from queue eventually.
                    logger.warning(f"S3 upload succeeded for {url}, but SQS delete failed.")
                    # Count as success from pipeline perspective, but log the issue.
                    processed_successfully += 1 
            else:
                # S3 save failed - DO NOT delete SQS message. Logged in save_to_s3.
                logger.error(f"Failed to save HTML for {url} to S3. Message will NOT be deleted.")
                failed_processing += 1
                # Report this specific message as failed back to SQS
                batch_item_failures.append({"itemIdentifier": message_id})
        else:
            # Fetch failed - DO NOT delete SQS message. Logged in fetch_html.
            logger.error(f"Failed to fetch HTML for {url}. Message will NOT be deleted.")
            failed_processing += 1
            # Report this specific message as failed back to SQS
            batch_item_failures.append({"itemIdentifier": message_id})


    logger.info(f"Processing complete. Success: {processed_successfully}, Failed: {failed_processing}")

    # Return structure tells SQS which specific messages failed processing
    # SQS will then make only those failed messages visible again for retry.
    return {"batchItemFailures": batch_item_failures}