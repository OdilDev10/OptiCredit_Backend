# Testing Guide — OptiCredit Backend

## 🧪 Test Setup

### 1. Install Development Dependencies
```bash
cd backend
uv pip install -r requirements-dev.txt
```

### 2. Run Tests
```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_services.py -v

# Run with coverage
pytest --cov=app tests/

# Run specific test
pytest tests/test_services.py::test_create_loan_application_valid -v
```

## 📊 Test Coverage

### Core Services Tests
- ✅ `tests/test_services.py`:
  - Loan Application Service (create, approve, reject)
  - Loan Service (create, generate installments)
  - Payment Service (submit, approve, reject)
  - Voucher Service (upload, OCR dispatch)

### Test Categories

#### Unit Tests (Services)
- Service logic validation
- Error handling
- Input validation
- Database operations

#### Repository Tests
- CRUD operations
- Query filters
- Relationships

#### API Endpoint Tests
- Request/response validation
- Authentication/authorization
- Error responses

## 🔄 Test Fixtures

### Database Fixtures
```python
@pytest.fixture
async def db_session():
    """Provides clean SQLite in-memory DB for each test."""
```

### Model Fixtures
```python
@pytest.fixture
async def lender(db_session):
    """Create test lender."""

@pytest.fixture
async def customer(db_session, lender):
    """Create test customer linked to lender."""
```

## 📋 Running Tests in CI/CD

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r backend/requirements-dev.txt
      - run: cd backend && pytest --cov=app
```

## 🎯 Testing Goals

**Phase 1 (Current):**
- Services: 80%+ coverage
- Repositories: 70%+ coverage

**Phase 2:**
- API endpoints: 75%+ coverage
- Integration tests

**Phase 3:**
- E2E tests with Playwright (FE + BE)
- Performance benchmarks

## 📚 Example Test Structure

```python
@pytest.mark.asyncio
async def test_create_loan_application_valid(db_session):
    """Descriptive test name."""
    # 1. ARRANGE: Setup test data
    lender = create_test_lender(db_session)
    customer = create_test_customer(db_session, lender)

    # 2. ACT: Execute the action
    service = LoanApplicationService(db_session)
    result = await service.create_application(...)

    # 3. ASSERT: Verify the result
    assert result["status"] == "submitted"
    assert result["requested_amount"] == 5000.0
```

## 🐛 Debugging Tests

### Using pytest flags
```bash
pytest -vv              # Extra verbose
pytest -s               # Show print statements
pytest -x               # Stop on first failure
pytest -k "loan"        # Run only tests matching "loan"
```

### Debug with pdb
```python
def test_something(db_session):
    result = service.some_method()
    import pdb; pdb.set_trace()  # Debugger pauses here
    assert result is not None
```

## ✅ Checklist Before Merging

- [ ] All tests pass: `pytest`
- [ ] Coverage >= 80%: `pytest --cov=app`
- [ ] Code style: `black app/` + `ruff check app/`
- [ ] Type checking: `mypy app/`
- [ ] No warnings: `pytest -W error`
