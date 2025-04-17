import json
import logging
import os
import re
import urllib.parse

import boto3
from bs4 import BeautifulSoup  # Requires deployment package

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client("s3")

# --- Configuration ---
# Get target S3 bucket name from environment variable
# ** IMPORTANT: Set this environment variable in your Lambda function config **
CHUNKS_S3_BUCKET = os.environ.get("CHUNKS_S3_BUCKET")
if not CHUNKS_S3_BUCKET:
    logger.critical("Environment variable CHUNKS_S3_BUCKET is not set.")
    # raise ValueError("Environment variable CHUNKS_S3_BUCKET is not set.")

# Chunking parameters (adjust as needed for your embedding model)
# Aim for chunks small enough for the model's context window,
# but large enough to contain meaningful context.
CHUNK_SIZE = 1000  # Target size in characters (approximate)
CHUNK_OVERLAP = 150 # Characters to overlap between chunks


def download_from_s3(bucket, key):
    """Downloads an object from S3 and returns its decoded content."""
    logger.info(f"Downloading s3://{bucket}/{key}")
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        # Assume UTF-8 encoding, handle potential errors gracefully
        return response["Body"].read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Failed to download s3://{bucket}/{key}: {e}")
        return None


def extract_text_from_html(html_content):
    """Parses HTML and extracts meaningful text using BeautifulSoup."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Remove common navigation, header, footer elements (heuristic)
        # Adjust selectors based on the common structure of your source sites
        for non_content in soup(
            ["nav", "footer", "header", "aside", "form", ".sidebar", "#sidebar"]
        ):
             try:
                 non_content.decompose()
             except Exception as e:
                 logger.warning(f"Could not decompose element: {e}")


        # Get text, joining paragraphs/blocks with newlines
        # Use strip=True to remove extra whitespace around text blocks
        text = soup.get_text(separator="\n", strip=True)

        # Optional: Further clean-up (e.g., remove excessive blank lines)
        text = re.sub(r"\n\s*\n", "\n\n", text).strip() # Consolidate blank lines

        logger.info(f"Extracted text length: {len(text)} characters.")
        return text

    except Exception as e:
        logger.error(f"Error parsing HTML with BeautifulSoup: {e}")
        return "" # Return empty string on parsing failure


def chunk_text_recursive(text, chunk_size, chunk_overlap, separators=None):
    """
    Recursively splits text into chunks trying different separators.
    A simplified approach inspired by LangChain's RecursiveCharacterTextSplitter.
    """
    if separators is None:
        # Define separators from largest (paragraph) to smallest (character)
        separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    final_chunks = []

    if not text:
        return []

    # Try the first separator
    current_separator = separators[0]
    next_separators = separators[1:]

    if current_separator == "" and not next_separators: # Base case: split by character if no other separator works
         # Split into chunks of size chunk_size with overlap
        for i in range(0, len(text), chunk_size - chunk_overlap):
            chunk = text[i:i + chunk_size]
            if chunk:
                final_chunks.append(chunk)
        return final_chunks


    # Split the text by the current separator
    try:
        # Handle empty separator case for final character split
        splits = re.split(f"({current_separator})", text) if current_separator else list(text)
        # Keep separators by re-combining: [part1, sep1, part2, sep2, part3...]
        combined_splits = []
        for i in range(0, len(splits), 2):
            part = splits[i]
            if i + 1 < len(splits):
                part += splits[i+1] # Add the separator back
            if part: # Avoid empty strings
                combined_splits.append(part)
        splits = combined_splits

    except Exception as e:
        logger.warning(f"Regex split failed for separator '{current_separator}': {e}. Falling back.")
        # Fallback if regex fails (e.g., complex separator)
        splits = [text] # Treat as one block and try next separator


    current_chunk = ""
    for part in splits:
        # If adding the next part doesn't exceed chunk_size
        if len(current_chunk) + len(part) <= chunk_size:
            current_chunk += part
        else:
            # If the current chunk is not empty, add it
            if current_chunk:
                final_chunks.append(current_chunk.strip())

            # If the part itself is larger than chunk_size, split it further
            if len(part) > chunk_size:
                 if next_separators: # Recurse if possible
                     final_chunks.extend(
                         chunk_text_recursive(part, chunk_size, chunk_overlap, next_separators)
                     )
                 else: # Cannot split further, add the oversized part
                     final_chunks.append(part.strip())
                 current_chunk = "" # Reset chunk after handling large part
            else:
                 # Start new chunk with the current part (with overlap from previous)
                 overlap_start_index = max(0, len(current_chunk) - chunk_overlap)
                 overlap = current_chunk[overlap_start_index:] if current_chunk else ""
                 current_chunk = (overlap + part).strip() # Start new chunk


    # Add the last remaining chunk if it exists
    if current_chunk:
        final_chunks.append(current_chunk.strip())

    # Filter out any potentially empty chunks after stripping
    return [chunk for chunk in final_chunks if chunk]


def save_chunk_to_s3(bucket, base_key, chunk_index, text_chunk, source_key):
    """Saves a text chunk as a JSON object to S3."""
    # Create a more structured key for chunks
    # e.g., example.com/page.html -> example.com/page.html/chunk_001.json
    chunk_key = f"{base_key}/chunk_{chunk_index:03d}.json"

    # Include metadata
    chunk_data = {
        "text": text_chunk,
        "metadata": {
            "source_s3_key": source_key, # Original HTML file key
            "chunk_number": chunk_index,
            # Add original URL here if you can reliably derive it from the key
            # "source_url": derive_url_from_key(source_key)
        },
    }

    logger.info(f"Saving chunk {chunk_index} to s3://{bucket}/{chunk_key}")
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=chunk_key,
            Body=json.dumps(chunk_data, indent=2),
            ContentType="application/json",
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to save chunk {chunk_index} to S3 "
            f"(Bucket: {bucket}, Key: {chunk_key}): {e}"
        )
        return False


def lambda_handler(event, context):
    """
    Lambda handler function triggered by S3 ObjectCreated events.
    Downloads HTML, extracts text, chunks it, and saves chunks to another S3 bucket.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    if not CHUNKS_S3_BUCKET:
        logger.error("CHUNKS_S3_BUCKET environment variable not set. Aborting.")
        return {"statusCode": 500, "body": "Configuration error"}

    success_count = 0
    failure_count = 0

    for record in event.get("Records", []):
        try:
            # Extract bucket name and object key from the S3 event
            source_bucket = record["s3"]["bucket"]["name"]
            # Object keys can have URL encoding (e.g., spaces as '+')
            source_key = urllib.parse.unquote_plus(
                record["s3"]["object"]["key"]
            )

            logger.info(f"Processing new object: s3://{source_bucket}/{source_key}")

            # 1. Download HTML from source S3
            html_content = download_from_s3(source_bucket, source_key)
            if html_content is None:
                logger.error(f"Failed to download or read {source_key}. Skipping.")
                failure_count += 1
                continue # Skip to the next record in the event

            # 2. Extract text content from HTML
            extracted_text = extract_text_from_html(html_content)
            if not extracted_text:
                logger.warning(f"No text extracted from {source_key}. Skipping.")
                # Don't count as failure, just nothing to process
                continue

            # 3. Chunk the extracted text
            text_chunks = chunk_text_recursive(
                extracted_text, CHUNK_SIZE, CHUNK_OVERLAP
            )
            logger.info(f"Split text into {len(text_chunks)} chunks.")

            if not text_chunks:
                logger.warning(f"Text chunking resulted in 0 chunks for {source_key}.")
                continue

            # 4. Save each chunk to the target S3 bucket
            # Use the original key as a base "directory" for the chunks
            base_chunk_key = source_key
            chunks_saved_successfully = 0
            for i, chunk in enumerate(text_chunks):
                save_success = save_chunk_to_s3(
                    CHUNKS_S3_BUCKET, base_chunk_key, i + 1, chunk, source_key # i+1 for 1-based index
                )
                if save_success:
                    chunks_saved_successfully += 1
                else:
                    # Logged within save_chunk_to_s3
                    pass # Continue trying to save other chunks

            if chunks_saved_successfully == len(text_chunks):
                logger.info(f"Successfully saved all {len(text_chunks)} chunks for {source_key}.")
                success_count += 1
            else:
                 logger.error(
                     f"Failed to save {len(text_chunks) - chunks_saved_successfully} out of "
                     f"{len(text_chunks)} chunks for {source_key}."
                 )
                 failure_count += 1


        except Exception as e:
            logger.exception(f"Unhandled exception processing record: {record}. Error: {e}")
            failure_count += 1
            # Continue to next record if possible

    logger.info(f"Processing finished. Success: {success_count}, Failures: {failure_count}")

    # S3 triggers don't typically require a specific return format unless used
    # with other services, but returning status can be helpful for monitoring.
    if failure_count > 0:
        # Indicate partial or full failure if necessary
        # Note: This doesn't automatically retry S3 events like SQS batchItemFailures
        return {"statusCode": 500, "body": f"Completed with {failure_count} failures."}
    else:
        return {"statusCode": 200, "body": "Processing successful."}