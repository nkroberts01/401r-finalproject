# Document Intelligence Pipeline

A comprehensive knowledge extraction and retrieval system that transforms documents into searchable, queryable knowledge using [Docling](https://github.com/DS4SD/docling) and large language models.

This pipeline converts various document formats into a unified structure, chunks content intelligently, creates semantic embeddings, and provides a natural language interface for retrieving information from your document collection.

## Key Features

- **Universal Document Processing**: Process PDF, DOCX, XLSX, PPTX, Markdown, HTML, images, and more with Docling
- **Smart Content Chunking**: Break documents into meaningful chunks while preserving context
- **Vector Embedding**: Create semantic embeddings for efficient similarity search
- **Persistent Storage**: Store document chunks and embeddings in LanceDB for fast retrieval
- **Natural Language Interface**: Query your documents using conversational language
- **Chat Memory**: Build contextual conversations about your documents
- **Advanced Understanding**: AI-powered layout analysis and table structure recognition
- **Flexible Output**: Export to HTML, Markdown, JSON, or plain text

## How It Works

This pipeline follows a sequential process:

1. **Document Extraction**: Parses documents using format-specific backends with layout preservation
2. **Content Chunking**: Intelligently segments documents into meaningful chunks
3. **Embedding Creation**: Generates vector embeddings that capture semantic meaning
4. **Storage**: Stores chunks and embeddings in LanceDB for efficient retrieval
5. **Retrieval**: Finds relevant document chunks based on similarity to queries
6. **Response Generation**: Uses LLMs to generate natural language answers from retrieved chunks

## Getting Started

### Prerequisites

1. Install the required packages:

```bash
pip install -r requirements.txt
```

### Running the Pipeline

Execute the scripts in order to build and query the document database:

1. **Extract document content**: `python 1-extraction.py`  
   Processes input documents using Docling and saves structured content

2. **Create document chunks**: `python 2-chunking.py`  
   Breaks documents into semantically meaningful chunks while preserving context

3. **Create embeddings**: `python 3-embedding.py`  
   Generates vector embeddings for each chunk and stores them in LanceDB

4. **Test search functionality**: `python 4-search.py`  
   Performs basic semantic search to verify the pipeline

5. **Launch the chat interface**: `streamlit run 5-chat.py`  
   Start the interactive chat interface at `http://localhost:8501`

## Document Processing Details

### Supported Input Formats

| Format | Description |
|--------|-------------|
| PDF | Native PDF documents with layout preservation |
| DOCX, XLSX, PPTX | Microsoft Office formats (2007+) |
| Markdown | Plain text with markup |
| HTML/XHTML | Web documents |
| Images | PNG, JPEG, TIFF, BMP |
| USPTO XML | Patent documents |
| PMC XML | PubMed Central articles |

Check out this [page](https://ds4sd.github.io/docling/supported_formats/) for an up to date list.

### Processing Pipeline

The standard document processing includes:

1. Document parsing with format-specific backend
2. Layout analysis using AI models
3. Table structure recognition
4. Metadata extraction
5. Content organization and structuring
6. Export formatting

## Use Cases

- **Enterprise Knowledge Base**: Create a searchable repository of company documents
- **Research Assistant**: Query across academic papers and technical documentation
- **Legal Document Analysis**: Extract and analyze information from legal contracts
- **Technical Support**: Build a system that can answer questions from product manuals
- **Content Creation**: Research and gather information from multiple sources efficiently

## Customization

Modify the configuration files to:
- Adjust chunking parameters for different document types
- Change embedding models for different performance/cost tradeoffs
- Customize the chat interface appearance and behavior
- Add additional processing steps to the pipeline