import json
import logging
import os
import urllib.parse
import time # For potential retries

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth, helpers

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration from Environment Variables ---
# ** IMPORTANT: Set these environment variables in your Lambda function config **
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT") # e.g., search-mydomain-xxxx.us-east-1.es.amazonaws.com
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX")     # e.g., my-rag-index
EMBEDDING_ENDPOINT_TYPE = os.environ.get("EMBEDDING_ENDPOINT_TYPE", "BEDROCK").upper() # 'BEDROCK' or 'SAGEMAKER'
# --- Conditional Env Vars ---
# Required if EMBEDDING_ENDPOINT_TYPE is 'SAGEMAKER'
SAGEMAKER_ENDPOINT_NAME = os.environ.get("SAGEMAKER_ENDPOINT_NAME")
# Required if EMBEDDING_ENDPOINT_TYPE is 'BEDROCK'
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v1") # Default to Titan v1

# --- Optional OpenSearch Auth ---
# If using Fine-Grained Access Control with HTTP basic auth
OPENSEARCH_USER = os.environ.get("OPENSEARCH_USER")
OPENSEARCH_PASSWORD = os.environ.get("OPENSEARCH_PASSWORD")

# --- AWS Clients ---
s3_client = boto3.client("s3")
# Initialize Bedrock/SageMaker client based on type
if EMBEDDING_ENDPOINT_TYPE == "BEDROCK":
    bedrock_runtime = boto3.client("bedrock-runtime")
    logger.info(f"Using Bedrock model: {BEDROCK_MODEL_ID}")
elif EMBEDDING_ENDPOINT_TYPE == "SAGEMAKER":
    sagemaker_runtime = boto3.client("sagemaker-runtime")
    logger.info(f"Using SageMaker endpoint: {SAGEMAKER_ENDPOINT_NAME}")
else:
    logger.error(f"Invalid EMBEDDING_ENDPOINT_TYPE: {EMBEDDING_ENDPOINT_TYPE}")
    raise ValueError("Invalid EMBEDDING_ENDPOINT_TYPE specified.")

# --- OpenSearch Client Setup ---
def get_opensearch_client():
    """Initializes and returns the OpenSearch client."""
    host = OPENSEARCH_ENDPOINT # Remove https:// if present for the host parameter
    if host.startswith("https://"):
        host = host[len("https://"):]
    
    auth = None
    if OPENSEARCH_USER and OPENSEARCH_PASSWORD:
        logger.info("Using HTTP Basic Authentication for OpenSearch.")
        auth = (OPENSEARCH_USER, OPENSEARCH_PASSWORD)
        # Ensure requests library is available if using basic auth over HTTPS
    else:
        logger.info("Using IAM Authentication for OpenSearch.")
        # Use AWS SDK credentials and sign requests with AWSV4SignerAuth
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, os.environ["AWS_REGION"], "es") # 'es' is the service name

    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=120 # Increase timeout for potentially long indexing
    )
    logger.info(f"OpenSearch client initialized for endpoint: {OPENSEARCH_ENDPOINT}")
    return client

opensearch_client = get_opensearch_client()

# --- Helper Functions ---

def download_and_parse_chunk(bucket, key):
    """Downloads JSON chunk from S3 and parses it."""
    logger.info(f"Downloading chunk: s3://{bucket}/{key}")
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except Exception as e:
        logger.error(f"Failed to download/parse s3://{bucket}/{key}: {e}")
        return None

def get_embedding_bedrock(text, model_id=BEDROCK_MODEL_ID):
    """Generates embedding using AWS Bedrock."""
    if not text: # Handle empty text case
        logger.warning("Received empty text for embedding, returning None.")
        return None
    try:
        # Ensure text is not excessively long (Bedrock models have limits)
        # This limit varies by model, check Bedrock documentation
        max_length = 8000 # Example limit, adjust as needed
        if len(text) > max_length:
            logger.warning(f"Text length ({len(text)}) exceeds max {max_length}. Truncating.")
            text = text[:max_length]

        # Body structure depends on the specific Bedrock model
        if "titan" in model_id:
            body = json.dumps({"inputText": text})
            accept = "application/json"
            contentType = "application/json"
        elif "cohere" in model_id: # Example for Cohere
             body = json.dumps({"texts": [text], "input_type": "search_document"})
             accept = "*/*"
             contentType = "application/json"
        # Add other model types as needed
        else:
             logger.error(f"Unsupported Bedrock model ID structure for body formatting: {model_id}")
             return None

        response = bedrock_runtime.invoke_model(
            body=body, modelId=model_id, accept=accept, contentType=contentType
        )
        response_body = json.loads(response.get("body").read())

        # Response structure also depends on the model
        if "titan" in model_id:
            embedding = response_body.get("embedding")
        elif "cohere" in model_id:
            embedding = response_body.get("embeddings")[0] # Cohere returns a list
        else:
             embedding = None # Should not happen if model check above worked

        if embedding:
             logger.info(f"Successfully generated Bedrock embedding. Vector length: {len(embedding)}")
        else:
             logger.error(f"Failed to get embedding from Bedrock response: {response_body}")

        return embedding

    except Exception as e:
        logger.exception(f"Error calling Bedrock ({model_id}): {e}")
        return None

def get_embedding_sagemaker(text, endpoint_name=SAGEMAKER_ENDPOINT_NAME):
    """Generates embedding using AWS SageMaker endpoint."""
    if not text:
        logger.warning("Received empty text for embedding, returning None.")
        return None
    try:
        # --- IMPORTANT ---
        # The request body format and response parsing depend HEAVILY
        # on the specific model and container used for your SageMaker endpoint.
        # This is a GENERIC example, likely needs adjustment.
        # Consult the documentation or examples for your specific model container.
        # Common pattern for HuggingFace models:
        request_body = {"inputs": text} # Or {"text_inputs": [text]}, etc.

        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Accept="application/json", # Or specific type if needed
            Body=json.dumps(request_body),
        )
        response_body = json.loads(response["Body"].read().decode("utf-8"))

        # --- Response Parsing (Highly Model Dependent) ---
        # Example 1: Embedding might be directly in the body
        # embedding = response_body

        # Example 2: Might be nested
        # embedding = response_body.get("embedding") # Or "embeddings", "vectors", etc.

        # Example 3: Might be a list of lists (common for sentence transformers)
        # embedding = response_body[0] if isinstance(response_body, list) and response_body else None

        # --- !!! REPLACE with actual parsing logic for YOUR endpoint !!! ---
        embedding = response_body # Placeholder - MUST BE ADJUSTED

        if embedding and isinstance(embedding, list):
             logger.info(f"Successfully generated SageMaker embedding. Vector length: {len(embedding)}")
        else:
             logger.error(f"Failed to extract valid embedding from SageMaker response: {response_body}")
             embedding = None # Ensure it's None if extraction failed

        return embedding

    except Exception as e:
        logger.exception(f"Error calling SageMaker endpoint ({endpoint_name}): {e}")
        return None

def index_documents_bulk(documents):
    """Indexes a list of documents into OpenSearch using the Bulk API."""
    if not documents:
        logger.info("No documents to index.")
        return True, 0

    logger.info(f"Preparing to index {len(documents)} documents in bulk.")
    actions = []
    for doc in documents:
        # Skip if essential parts are missing
        if not doc.get("embedding") or not doc.get("text"):
            logger.warning(f"Skipping document due to missing text or embedding: {doc.get('id', 'Unknown ID')}")
            continue

        action = {
            "_index": OPENSEARCH_INDEX,
            # Optionally provide an ID, otherwise OpenSearch generates one
            # Using the S3 key as ID can help prevent duplicates if Lambda retries
            "_id": doc.get("id"),
            "_source": {
                "embedding_vector": doc["embedding"],
                "text_chunk": doc["text"],
                "metadata": doc["metadata"],
            },
        }
        actions.append(action)

    if not actions:
        logger.warning("No valid actions generated for bulk indexing.")
        return True, 0 # No failures, but nothing done

    try:
        success_count, failed_items = helpers.bulk(
            opensearch_client, actions, chunk_size=100, request_timeout=120
        )
        logger.info(f"Bulk indexing result: Success={success_count}, Failures={len(failed_items)}")
        if failed_items:
            # Log first few failures for diagnosis
            logger.error(f"First few failed items: {failed_items[:5]}")
            return False, len(failed_items) # Indicate failure
        return True, 0 # Indicate success

    except Exception as e:
        logger.exception(f"Error during OpenSearch bulk indexing: {e}")
        return False, len(actions) # Assume all failed if the bulk call itself errored


# --- Main Handler ---

def lambda_handler(event, context):
    """
    Lambda handler function triggered by S3 ObjectCreated events on chunks bucket.
    Downloads chunk, generates embedding, indexes into OpenSearch.
    """
    logger.info(f"Received event with {len(event.get('Records', []))} records.")

    # Validate essential configuration
    if not OPENSEARCH_ENDPOINT or not OPENSEARCH_INDEX:
        logger.critical("OpenSearch endpoint or index not configured. Aborting.")
        return {"statusCode": 500, "body": "Configuration error"}
    if EMBEDDING_ENDPOINT_TYPE == "SAGEMAKER" and not SAGEMAKER_ENDPOINT_NAME:
         logger.critical("SageMaker endpoint name not configured. Aborting.")
         return {"statusCode": 500, "body": "Configuration error"}

    documents_to_index = []
    total_processed = 0
    total_failed = 0

    for record in event.get("Records", []):
        try:
            source_bucket = record["s3"]["bucket"]["name"]
            source_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
            logger.info(f"Processing object: s3://{source_bucket}/{source_key}")

            # 1. Download and parse the JSON chunk
            chunk_data = download_and_parse_chunk(source_bucket, source_key)
            if chunk_data is None:
                total_failed += 1
                continue # Skip to next record

            text_chunk = chunk_data.get("text")
            metadata = chunk_data.get("metadata", {}) # Get metadata or empty dict

            if not text_chunk:
                logger.warning(f"No text found in chunk {source_key}. Skipping.")
                continue # Nothing to embed

            # 2. Generate embedding
            embedding = None
            if EMBEDDING_ENDPOINT_TYPE == "BEDROCK":
                embedding = get_embedding_bedrock(text_chunk)
            elif EMBEDDING_ENDPOINT_TYPE == "SAGEMAKER":
                embedding = get_embedding_sagemaker(text_chunk)

            if embedding is None:
                logger.error(f"Failed to generate embedding for {source_key}. Skipping.")
                total_failed += 1
                continue # Cannot index without embedding

            # 3. Prepare document for OpenSearch Bulk API
            # Use the S3 object key as the document ID for potential idempotency
            doc_id = source_key
            documents_to_index.append({
                "id": doc_id,
                "text": text_chunk,
                "embedding": embedding,
                "metadata": metadata
            })
            total_processed += 1

        except Exception as e:
            logger.exception(f"Unhandled exception processing record: {record}. Error: {e}")
            total_failed += 1
            # Continue to next record if possible

    # 4. Index all collected documents in bulk
    bulk_success, bulk_failures = index_documents_bulk(documents_to_index)
    total_failed += bulk_failures # Add bulk indexing failures to total

    logger.info(
        f"Processing finished. Records processed: {total_processed}, "
        f"Total failures (download/embed/index): {total_failed}"
    )

    if total_failed > 0:
        # Indicate partial or full failure
        return {"statusCode": 500, "body": f"Completed with {total_failed} failures."}
    else:
        return {"statusCode": 200, "body": "Processing successful."}

