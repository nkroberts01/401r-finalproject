import json
import logging
import os
import xml.etree.ElementTree as ET

# Using standard library for HTTP requests for simplicity in Lambda
# If complex headers/retries are needed, package 'requests' library instead
import urllib.request
import urllib.error

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients (outside handler for potential reuse)
sqs_client = boto3.client("sqs")

# --- Configuration ---
# Get SQS Queue URL from environment variable
# ** IMPORTANT: Set this environment variable in your Lambda function configuration **
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")
if not SQS_QUEUE_URL:
    # Log critically if the essential env var is missing
    logger.critical("Environment variable SQS_QUEUE_URL is not set.")
    # Optionally raise an exception to halt execution if preferred
    # raise ValueError("Environment variable SQS_QUEUE_URL is not set.")

# Namespace for standard sitemaps
SITEMAP_NS = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

def fetch_sitemap(url):
    """Fetches content from a given URL."""
    logger.info(f"Fetching sitemap from: {url}")
    try:
        # Add a user-agent header to avoid potential blocking
        headers = {
            "User-Agent": "AWS Lambda Sitemap Parser Bot (https://aws.amazon.com/lambda/)"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:  # 15s timeout
            if response.status == 200:
                logger.info(f"Successfully fetched sitemap (Status: 200)")
                return response.read()
            else:
                logger.error(
                    f"Failed to fetch sitemap. Status code: {response.status}"
                )
                return None
    except urllib.error.URLError as e:
        logger.error(f"Error fetching sitemap URL {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during fetch: {e}")
        return None


def parse_sitemap_xml(xml_content):
    """Parses XML content and extracts URLs from <loc> tags."""
    urls = []
    try:
        root = ET.fromstring(xml_content)
        # Find all <loc> elements within the defined namespace
        for loc in root.findall(".//ns:loc", SITEMAP_NS):
            if loc.text:
                urls.append(loc.text.strip())
        logger.info(f"Parsed {len(urls)} URLs from sitemap.")
        return urls
    except ET.ParseError as e:
        logger.error(f"Failed to parse sitemap XML: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred during XML parsing: {e}")
        return []


def send_urls_to_sqs(urls_to_send):
    """Sends a list of URLs to the configured SQS queue."""
    if not SQS_QUEUE_URL:
        logger.error("SQS Queue URL is not configured. Cannot send messages.")
        return 0, len(urls_to_send)  # 0 sent, all failed

    sent_count = 0
    failed_count = 0
    max_batch_size = 10  # SQS SendMessageBatch limit
    
    for i in range(0, len(urls_to_send), max_batch_size):
        batch_urls = urls_to_send[i:i + max_batch_size]
        entries = []
        for idx, url in enumerate(batch_urls):
            # Ensure message ID is unique within the batch
            message_id = f"url-{i + idx}" 
            entries.append({"Id": message_id, "MessageBody": url})

        if not entries:
            continue

        try:
            response = sqs_client.send_message_batch(
                QueueUrl=SQS_QUEUE_URL, Entries=entries
            )
            
            success_count = len(response.get("Successful", []))
            sent_count += success_count
            
            failures = response.get("Failed", [])
            if failures:
                failed_count += len(failures)
                for failure in failures:
                    logger.error(
                        f"Failed to send message ID {failure['Id']} to SQS. "
                        f"Code: {failure.get('Code')}, "
                        f"Message: {failure.get('Message')}"
                    )
            
            logger.info(f"Sent batch of {success_count} URLs to SQS. {len(failures)} failures in batch.")

        except Exception as e:
            logger.error(f"Failed to send batch to SQS: {e}")
            # Assume all messages in this batch failed if the API call itself fails
            failed_count += len(entries)

    logger.info(
        f"Finished sending URLs. Total Sent: {sent_count}, Total Failed: {failed_count}"
    )
    return sent_count, failed_count


def lambda_handler(event, context):
    """
    Lambda handler function.
    Expects event data containing either 'sitemap_url' or 'urls' list.
    Example event (API Gateway):
    { "body": "{\"sitemap_url\": \"http://example.com/sitemap.xml\"}" }
    Example event (Direct Invoke/Other):
    { "sitemap_url": "http://example.com/sitemap.xml" }
    { "urls": ["http://example.com/page1", "http://example.com/page2"] }
    """
    logger.info(f"Received event: {json.dumps(event)}")

    if not SQS_QUEUE_URL:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": "Configuration error: SQS_QUEUE_URL not set."}
            ),
        }

    urls_to_process = []
    sitemap_url = None
    direct_urls = None

    # --- Input Handling ---
    # Check for API Gateway proxied event
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
            sitemap_url = body.get("sitemap_url")
            direct_urls = body.get("urls")
        except json.JSONDecodeError:
            logger.warning("Event body is a string but not valid JSON.")
            # Try to get from top-level event as fallback
            sitemap_url = event.get("sitemap_url")
            direct_urls = event.get("urls")
    else:
        # Handle direct invocation or other event sources
        sitemap_url = event.get("sitemap_url")
        direct_urls = event.get("urls")

    # --- Processing Logic ---
    if sitemap_url:
        xml_content = fetch_sitemap(sitemap_url)
        if xml_content:
            urls_to_process = parse_sitemap_xml(xml_content)
        else:
            # Fetch failed, error already logged
            pass # Continue to check direct_urls or finish
            
    # If no URLs from sitemap (or no sitemap provided), check for direct URLs
    if not urls_to_process and direct_urls:
        if isinstance(direct_urls, list):
            logger.info(f"Processing {len(direct_urls)} direct URLs provided in event.")
            urls_to_process = direct_urls
        else:
            logger.warning("'urls' provided in event but is not a list.")

    # --- Output ---
    if not urls_to_process:
        logger.warning("No URLs found to process from sitemap or direct input.")
        return {
            "statusCode": 400, # Bad request or no data
            "body": json.dumps({"message": "No URLs found to process."}),
        }

    sent_count, failed_count = send_urls_to_sqs(urls_to_process)

    if failed_count > 0:
        status_code = 500 # Indicate partial or complete failure
    else:
        status_code = 200 # All successful

    return {
        "statusCode": status_code,
        "body": json.dumps(
            {
                "message": f"Processed {len(urls_to_process)} URLs.",
                "sent_to_sqs": sent_count,
                "failed_to_send": failed_count,
            }
        ),
    }