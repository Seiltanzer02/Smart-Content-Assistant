import sys
sys.path.append('.')
try:
    from services.ideas_service import generate_content_plan, get_saved_ideas, save_suggested_idea, save_suggested_ideas_batch
    with open('import_result.txt', 'w') as f:
        f.write("SUCCESS: Module services.ideas_service successfully imported!")
except Exception as e:
    with open('import_result.txt', 'w') as f:
        f.write(f"ERROR: Import error: {e}") 