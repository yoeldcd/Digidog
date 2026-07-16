# Python development practices

## Clean architecture principles

- **Separation of Concerns**: We maintain a strict boundary between database structures (SQLAlchemy ORM models), business rules orchestration (Services), and external interfaces/data transport contracts (DTOs).
- **Core Domain Protection**: Changes in the database layout or external API endpoints must not impact core business logic.
- **Dependency Inversion**: Service layers communicate with external APIs and services via specialized connector adapters, ensuring business code remains testable and detached from network protocols.
- **Smart Minimun Codebases**: Allways possible manage files under line number range of 500 ~ 700 lines at maximun. Decompose large files in cohesive modular architecture.

---

## Python technology stack

- **Language Core**: Python v3.9+
- **API Frame**: FastAPI
- **Data Persistence**: SQLAlchemy ORM
- **AI Orchestration**: LangChain, SpaCy

---

## Dependency import structure

- Divide imports into commented categories to trace third-party and internal dependencies clearly:

  ```python
  # Standard Libraries Imports
  ...

  # Third-party Libraries Imports
  ...

  # Application Utilities Imports
  ...

  # Application Modules Imports
  ...
  ```

- Sort imports alphabetically inside each group.
- Use absolute imports for external libraries and relative imports for local modules.

---

## General documentation policy (PEP 257)

- Write all documentation in **English**.
- Follow PEP 257 docstring conventions.
- **Classes**: Detail general responsibilities followed by an `Attributes:` block.
- **Functions/Methods**: Document `Args:`, `Returns:`, and optionally `Example:` or `Raises:`.

### Docstring format contract

- Write technical, declarative, and non-redundant English description blocks.
- **Description Block**: A 1 or 2 sentence summary describing the routine's purpose, wrapping parameters or structures in backticks (e.g. `"Search database for the`Worker` matching `worker_id`."`).

#### Args section

- List parameters specifying names, type annotations, and detailed usage descriptions (including bounds and default values).
- *Example*:

  ```python
  def set_window_dimensions(width: int | str = 10, height: int | str = 10):
      """
      Set the window dimensions. Cast string values to integers.
      
      Args:
          width (int | str): A number describing the window width. 
                             Optionally receives a parsable numeric string. Defaults to 10.
          height (int | str): A number describing the window height. 
                              Optionally receives a parsable numeric string. Defaults to 10.
      """
      ...
  ```

#### Returns section

- Document returned types, ranges, or conditional responses (e.g., matching HTTP status codes to DTO schemas).
- *Example*:

  ```txt
  Returns:
      (Status 200) API response containing {ModelNameDTO} retrieved.
      (Status 404) API response describing a retrieval failure.
  ```

---

## Code formatting & typing

- Maximum line length: 120 characters.
- Indentation: 4 spaces.
- Blank lines: 2 blank lines between classes and top-level functions.
- Type annotations: Mandatory type declarations on parameters and return signatures, using native union (`|`) and optional (`| None`) types.

### Nomenclature style

- **Classes**: `PascalCase`
- **Functions, Methods & Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private Class Fields**: `_leading_underscore`
- **ORM Database models**: Prefix with `db_` (e.g., `db_worker`) to differentiate from logic schemas.
- **DTO schemas**: Suffix with `_dto` (e.g., `worker_dto`).

### Variable logic & assignment

- Do not assign compound structures (dicts, lists) directly to arguments. Assign to local scope variables first.
- Enforce trailing commas `,` on lists or dictionaries with more than 3 elements to trigger multi-line formatting.
- Prefer keyword arguments (kwargs) over positional parameters.
- Keep route handler views lightweight; delegate query extraction and logical validation to helper operations.

#### View logic example

```python
# Standard library imports
from uuid import UUID

# Application module imports
from server.api.wrappers import wrap_db_document
from server.api.schemas import DocumentDTO
from server.models import DBDocument

def get_db_document_by_id(db_document_uuid: UUID) -> DBDocument:
    """
    Retrieve document from database.
    
    Args:
        db_document_uuid (UUID): The unique UUID of the document.
        
    Returns:
        DBDocument: The retrieved database record.
    """
    db_filters: dict = {
        'id': db_document_uuid,
    }
    return db.get_record(filters=db_filters)

@api.get("/app/documents/{document_id}")
async def get_document_data(document_id: str):
    """
    Fetch and serialize a document.
    
    Args:
        document_id (str): Raw hexadecimal UUID string from client.
        
    Returns:
        APIResponse: JSON wrapper containing DocumentDTO.
    """
    # Declare scope variables
    db_document_uuid: UUID
    db_document: DBDocument
    document_dto: DocumentDTO
    
    # Validate given document identifier
    try:
        db_document_uuid = UUID(hex=document_id)
    except ValueError:
        return APIResponse(
            code=406,
            message="Invalid document ID format."
        )
    
    # Retrieve document from database
    db_document = get_db_document_by_id(db_document_uuid=db_document_uuid)
    
    # Check document existence
    if not db_document:
        return APIResponse(
            code=404,
            message=f"Document with id `{document_id}` not found."
        )
    
    # Wrap database record as DTO
    document_dto = wrap_db_document(db_document)
    
    # Return serialized JSON
    return APIResponse(
        data=document_dto.model_dump()
    )
```

---

## Data schemas & ORM modelling

- Keep database schemas separate from DTO contract schemas.
- DTO schemas inherit from Pydantic `BaseModel` and utilize `ConfigDict(from_attributes=True)` to convert ORM models securely.
- Document all class variables and specify default values using Pydantic `Field()`.
- Avoid circular serialization loops by utilizing primary key IDs in nested relationships instead of deep model nesting.

---

## Function & routine contracts

- Specify explicit typing contracts on parameters and returns.

```python
def convert_model(source: SourceModel) -> TargetDTO:
    """
    Convert SourceModel instance to TargetDTO.

    Args:
        source: The source model instance to map.

    Returns:
        TargetDTO: The mapped output data object.

    Example:
        >>> result = convert_model(source_instance)
    """
    # Declare local variables at top of scope
    variable1: int = 2
    variable2: int = 7
    ...
```

### Wrappers

- Prefix data transformer helpers with `wrap_[model_name]`.
- Handle context operations inside boundary scopes (e.g. `with database.bind()`).
- Verify data integrity by parsing results through `.model_validate()`.

---

## Class boundaries

- Declare class variables first, followed by constructors, logical groups, properties, and finally private methods.

```python
class ExampleDTO(BaseModel):
    """
    Data Transfer Object schema for example instances.

    Attributes:
        field1: Primary text value.
        field2: Optional status code.
    """

    field1: str = Field(...)
    """Primary text value"""

    field2: int = Field(default=0)
    """Optional status code"""
```
