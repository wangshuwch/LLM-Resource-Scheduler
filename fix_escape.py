
import os

def fix_html_entities(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    replacements = {
        '&lt;': '&lt;',
        '&gt;': '&gt;',
        '&amp;': '&amp;',
        '&le;': '&lt;=',
        '&ge;': '&gt;=',
        '&ne;': '!=',
        '&eq;': '=='
    }
    
    for html_entity, python_op in replacements.items():
        content = content.replace(html_entity, python_op)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {file_path}")
        return True
    return False

def scan_and_fix_directory(root_dir):
    python_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                filepath = os.path.join(dirpath, filename)
                python_files.append(filepath)
    
    fixed_count = 0
    for file_path in python_files:
        if fix_html_entities(file_path):
            fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.abspath(__file__))
    scan_and_fix_directory(root_dir)

