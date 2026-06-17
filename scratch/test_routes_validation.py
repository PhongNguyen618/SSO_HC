import sys
from unittest.mock import MagicMock

# UTF-8 encoding on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from backend.database import SessionLocal, CompetitionEvent
from backend.main import index, rules_page, register_page, profile_page, export_excel

def test_routes():
    db = SessionLocal()
    mock_request = MagicMock()
    # Mock template responses to avoid rendering issues in testing environment
    import backend.main
    original_templates = backend.main.templates
    backend.main.templates = MagicMock()
    
    try:
        print("Testing routes with various event_id values...")
        
        # Test event_id = ""
        print("\n1. Testing event_id = '' (empty string)...")
        index(request=mock_request, event_id="", db=db)
        print(" -> index ok")
        rules_page(request=mock_request, event_id="", db=db)
        print(" -> rules_page ok")
        register_page(request=mock_request, event_id="", db=db)
        print(" -> register_page ok")
        
        # Test event_id = None
        print("\n2. Testing event_id = None...")
        index(request=mock_request, event_id=None, db=db)
        print(" -> index ok")
        rules_page(request=mock_request, event_id=None, db=db)
        print(" -> rules_page ok")
        register_page(request=mock_request, event_id=None, db=db)
        print(" -> register_page ok")

        # Test event_id = "abc" (invalid int)
        print("\n3. Testing event_id = 'abc'...")
        index(request=mock_request, event_id="abc", db=db)
        print(" -> index ok")
        rules_page(request=mock_request, event_id="abc", db=db)
        print(" -> rules_page ok")
        register_page(request=mock_request, event_id="abc", db=db)
        print(" -> register_page ok")

        print("\nAll routes executed successfully without throwing validation errors!")
        
    except Exception as e:
        print(f"\nFailed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        backend.main.templates = original_templates
        db.close()

if __name__ == "__main__":
    test_routes()
