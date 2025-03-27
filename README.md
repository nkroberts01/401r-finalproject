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
- **PDF Highlighting**: View source documents with relevant sections automatically highlighted

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

1. **Python Environment**: Python 3.8+ recommended
2. **OpenAI API Key**: Required for embeddings and LLM responses (you'll be prompted to enter this in the interface)
3. **Dependencies**: Set up your environment using the instructions below

### Environment Setup

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip3 install -r requirements.txt
```

### Running the Pipeline

The project consists of modular Python files that can be imported directly or used in sequence:

1. **Extract document content**: Uses `extraction.py`  
   Processes input documents using Docling and saves structured content

2. **Create document chunks**: Uses `chunking.py`  
   Breaks documents into semantically meaningful chunks while preserving context

3. **Create embeddings**: Uses `embedding.py`  
   Generates vector embeddings for each chunk and stores them in LanceDB

4. **Launch the chat interface**: 
   ```bash
   streamlit run chat.py
   ```
   Start the interactive chat interface at `http://localhost:8501`

### Interactive Streamlit Interface

The Streamlit interface (`chat.py`) provides:

- Document upload functionality for PDFs, DOCX, and TXT files
- Automatic processing of uploaded documents
- Conversational interface for querying documents
- Interactive PDF viewer with automatic highlighting of relevant sections
- Temperature control for adjusting AI response creativity
- Source attribution with page numbers and section titles
- Prompt to enter your OpenAI API key (which will be saved automatically)

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

### Models Used

- **Embedding**: OpenAI's `text-embedding-3-large` for vector embeddings
- **Chat Completion**: OpenAI's `gpt-4o-mini` for generating responses (configurable)
- **Tokenizer**: OpenAI's `cl100k_base` for text chunking

## Project Structure

- `extraction.py`: Document extraction functionality
- `chunking.py`: Text chunking with context preservation
- `embedding.py`: Vector embedding creation and storage
- `chat.py`: Streamlit interface for document Q&A
- `utils/`: Helper utilities including tokenization and sitemap processing

## Use Cases

- **Enterprise Knowledge Base**: Create a searchable repository of company documents
- **Research Assistant**: Query across academic papers and technical documentation
- **Legal Document Analysis**: Extract and analyze information from legal contracts
- **Technical Support**: Build a system that can answer questions from product manuals
- **Content Creation**: Research and gather information from multiple sources efficiently

## Customization

Modify the code to:
- Adjust chunking parameters for different document types (in `chunking.py`)
- Change embedding models for different performance/cost tradeoffs (in `embedding.py`)
- Customize the chat interface appearance and behavior (in `chat.py`)
- Add additional processing steps to the pipeline

## Troubleshooting

- **Missing API Key**: If the OpenAI API key is missing, you'll be prompted to enter it in the Streamlit interface (no need to create a .env file manually)
- **PDF Highlighting Issues**: Ensure PyMuPDF is properly installed with `pip install PyMuPDF`
- **Storage Issues**: Check that the `data/` directory exists and has proper permissions
- **Large Document Processing**: For very large documents, you may need to adjust the `MAX_TOKENS` constant in `chunking.py`